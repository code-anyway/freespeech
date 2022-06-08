import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple

from deepgram import Deepgram
from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech
from google.cloud.speech_v1.types.cloud_speech import LongRunningRecognizeResponse
from google.cloud.texttospeech_v1.types import SynthesizeSpeechResponse

from freespeech import env
from freespeech.lib import concurrency, media
from freespeech.lib.storage import obj
from freespeech.lib.text import chunk, remove_symbols
from freespeech.types import (
    Audio,
    Character,
    Event,
    Language,
    ServiceProvider,
    TranscriptionModel,
    Voice,
    url,
    is_character
)

logger = logging.getLogger(__name__)

MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit

# Let's give voices real names and map them to API-specific names
VOICES = {
    "Ada Lovelace": {
        "en-US": "en-US-Wavenet-F",
        "ru-RU": "ru-RU-Wavenet-E",
        "pt-PT": "pt-PT-Wavenet-D",
        "de-DE": "de-DE-Wavenet-C",
        "es-US": "es-US-Wavenet-A",
    },
    "Grace Hopper": {
        "en-US": "en-US-Wavenet-C",
        "ru-RU": "ru-RU-Wavenet-C",
        "pt-PT": "pt-PT-Wavenet-A",
        "de-DE": "de-DE-Wavenet-F",
        "uk-UA": "uk-UA-Wavenet-A",
        "es-US": "es-US-Wavenet-A",
    },
    "Alan Turing": {
        "en-US": "en-US-Wavenet-I",
        "ru-RU": "ru-RU-Wavenet-D",
        "pt-PT": "pt-PT-Wavenet-C",
        "de-DE": "de-DE-Wavenet-B",
        "es-US": "es-US-Wavenet-B",
    },
    "Alonzo Church": {
        "en-US": "en-US-Wavenet-D",
        "ru-RU": "ru-RU-Wavenet-B",
        "pt-PT": "pt-PT-Wavenet-B",
        "de-DE": "de-DE-Wavenet-D",
        "es-US": "es-US-Wavenet-C",
    },
}

GOOGLE_CLOUD_ENCODINGS = {
    "LINEAR16": speech_api.RecognitionConfig.AudioEncoding.LINEAR16,
    "WEBM_OPUS": speech_api.RecognitionConfig.AudioEncoding.WEBM_OPUS,
}

# When synthesizing speech to match duration, this is the maximum delta.
SYNTHESIS_ERROR_MS = 200

SPEECH_RATE_MINIMUM = 0.7
SPEECH_RATE_MAXIMUM = 1.3

# Number of retries when iteratively adjusting speaking rate.
SYNTHESIS_RETRIES = 10

# Speech-to-text API call timeout.
TRANSCRIBE_TIMEOUT_SEC = 300


@cache
def supported_voices() -> Dict[str, Sequence[str]]:
    client = texttospeech.TextToSpeechClient()

    # Performs the list voices request
    response = client.list_voices()

    return {voice.name: voice.language_codes for voice in response.voices}


async def transcribe(
    uri: str,
    audio: Audio,
    lang: Language,
    model: TranscriptionModel = "default",
    provider: ServiceProvider = "Google",
) -> Sequence[Event]:
    """Transcribe audio.

    Args:
        uri: URI to the file. Supported: `gs://bucket/path`
        audio: audio stream info.
        lang: speaker's language-region (i.e. en-US, pt-BR)
            as per https://www.rfc-editor.org/rfc/rfc5646
        model: transcription model (default: `"default"`).
            https://cloud.google.com/speech-to-text/docs/transcription-model

    Returns:
        Transcript containing timed phrases as `List[Event]`.
    """

    if audio.num_channels != 1:
        raise ValueError(
            ("Audio should be mono for best results. " "Set audio.num_channels to 1.")
        )

    match provider:
        case "Google":
            return await _transcribe_google(uri, audio, lang, model)
        case "Deepgram":
            return await _transcribe_deepgram(uri, audio, lang, model)
        case "Azure":
            raise NotImplementedError()
        case _:
            raise ValueError(f"Unsupported provider: {provider}")


async def _transcribe_deepgram(
    uri: url, audio: Audio, lang: Language, model: TranscriptionModel
):
    # For more info see language section of
    # https://developers.deepgram.com/api-reference/#transcription-prerecorded
    LANGUAGE_OVERRIDE = {
        "uk-UA": "uk",
        "ru-RU": "ru"
    }

    deepgram_lang = LANGUAGE_OVERRIDE.get(lang, None) or lang

    if model in ("default", "latest_long"):
        model = "general"

    if audio.encoding == "LINEAR16":
        mime_type = "audio/wav"
    else:
        raise ValueError(f"Unsupported audio encoding: {audio.encoding}")

    deepgram = Deepgram(env.get_deepgram_token())

    with TemporaryDirectory() as tmp_dir:
        file_path = await obj.get(uri, tmp_dir)

        with open(file_path, "rb") as buffer:
            source = {"buffer": buffer, "mimetype": mime_type}
            response = await deepgram.transcription.prerecorded(
                source,
                {
                    "punctuate": True,
                    "language": deepgram_lang,
                    "model": model,
                    "profanity_filter": False,
                    "diarize": True,
                    "utterances": True,
                    "utt_split": 1.4,
                },
            )

    characters = ("Alan Turing", "Alonzo Church")

    events = []
    for utterance in response["results"]["utterances"]:
        character = characters[int(utterance["speaker"]) % len(characters)]
        assert is_character(character)

        event = Event(
            time_ms=round(float(utterance["start"]) * 1000),
            duration_ms=round(
                float(utterance["end"] - float(utterance["start"])) * 1000
            ),
            chunks=[utterance["transcript"]],
            voice=Voice(character=character),
        )
        events += [event]

    return events


async def _transcribe_google(
    uri: url, audio: Audio, lang: Language, model: TranscriptionModel
) -> Sequence[Event]:
    if audio.encoding not in GOOGLE_CLOUD_ENCODINGS:
        raise ValueError(
            (
                f"Invalid audio encoding: {audio.encoding} "
                f"Expected values {','.join(GOOGLE_CLOUD_ENCODINGS)}."
            )
        )

    client = speech_api.SpeechClient()

    try:

        def _api_call() -> LongRunningRecognizeResponse:
            operation = client.long_running_recognize(
                config=speech_api.RecognitionConfig(
                    audio_channel_count=audio.num_channels,
                    encoding=GOOGLE_CLOUD_ENCODINGS[audio.encoding],
                    sample_rate_hertz=audio.sample_rate_hz,
                    language_code=lang,
                    model=model,
                    enable_automatic_punctuation=True,
                    # TODO (astaff): are there any measurable gains
                    # from adjusting the hyper parameters?
                    # metadata=speech_api.RecognitionMetadata(
                    #     recording_device_type=speech_api.RecognitionMetadata.RecordingDeviceType.SMARTPHONE,  # noqa: E501
                    #     original_media_type=speech_api.RecognitionMetadata.OriginalMediaType.VIDEO,  # noqa: E501
                    # )
                ),
                audio=speech_api.RecognitionAudio(uri=uri),
            )
            result = operation.result(timeout=TRANSCRIBE_TIMEOUT_SEC)  # type: ignore
            assert isinstance(
                result, LongRunningRecognizeResponse
            ), f"type(result)={type(result)}"

            return result

        response = await concurrency.run_in_thread_pool(_api_call)
    except google_api_exceptions.NotFound:
        raise ValueError(f"Requested entity not found {uri}")

    current_time_ms = 0
    events = []

    for result in response.results:
        end_time_ms = int(result.result_end_time.total_seconds() * 1000)
        event = Event(
            time_ms=current_time_ms,
            duration_ms=end_time_ms - current_time_ms,
            chunks=[result.alternatives[0].transcript],
        )
        current_time_ms = end_time_ms
        events += [event]
    return events


def is_valid_ssml(text: str) -> bool:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False

    return root.tag == "speak"


def text_to_ssml_chunks(text: str, chunk_length: int) -> Sequence[str]:
    inner = re.sub(r"#(\d+(\.\d+)?)#", r'<break time="\1s" />', text)

    def wrap(text: str) -> str:
        result = f"<speak>{text}</speak>"
        assert is_valid_ssml(result), f"text={text} result={result}"
        return result

    overhead = len(wrap(""))

    return [wrap(c) for c in chunk(text=inner, max_chars=chunk_length - overhead)]


async def synthesize_text(
    text: str,
    duration_ms: int,
    voice: Character,
    lang: str,
    pitch: float,
    output_dir: Path | str,
) -> Tuple[Path, Voice]:
    chunks = text_to_ssml_chunks(text, chunk_length=MAX_CHUNK_LENGTH)

    if voice not in VOICES:
        raise ValueError(
            (f"Unsupported voice: {voice}\n" f"Supported voices: {VOICES}")
        )

    if lang not in VOICES[voice]:
        raise ValueError(
            (f"Unsupported lang {lang} for {voice}\n" f"Supported voices: {VOICES}")
        )

    google_voice = VOICES[voice][lang]
    all_google_voices = supported_voices()

    if (
        google_voice not in all_google_voices
        or lang not in all_google_voices[google_voice]
    ):
        raise ValueError(
            (
                f"Google Speech Synthesis API "
                "doesn't support {lang} for voice {voice}\n"
                f"Supported values: {all_google_voices}"
            )
        )

    async def _synthesize_step(rate: float, retries: int | None) -> Tuple[Path, float]:
        if retries is not None and retries < 0:
            raise RuntimeError(
                (
                    "Unable to converge while adjusting speaking rate "
                    f"after {SYNTHESIS_RETRIES} attempts."
                    f"text={text} duration={duration_ms}"
                )
            )

        if rate < SPEECH_RATE_MINIMUM:
            return await _synthesize_step(SPEECH_RATE_MINIMUM, retries=None)

        if rate > SPEECH_RATE_MAXIMUM:
            return await _synthesize_step(SPEECH_RATE_MAXIMUM, retries=None)

        def _api_call(phrase: str) -> SynthesizeSpeechResponse:
            client = texttospeech.TextToSpeechClient()
            return client.synthesize_speech(
                input=texttospeech.SynthesisInput(ssml=phrase),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=lang, name=google_voice
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    pitch=pitch,
                    speaking_rate=rate,
                ),
            )

        responses = await asyncio.gather(
            *[concurrency.run_in_thread_pool(_api_call, phrase) for phrase in chunks]
        )

        with TemporaryDirectory() as tmp_dir:
            files = [f"{media.new_file(tmp_dir)}.wav" for _ in responses]
            for file, response in zip(files, responses):
                with open(file, "wb") as fd:
                    fd.write(response.audio_content)
            audio_file = await media.concat(files, output_dir)

        (audio, *_), _ = media.probe(audio_file)
        assert isinstance(audio, Audio)

        if retries is None or abs(audio.duration_ms - duration_ms) < SYNTHESIS_ERROR_MS:
            return Path(audio_file), rate
        else:
            logger.warning(
                f"retrying delta={audio.duration_ms - duration_ms} rate={rate}"
            )
            rate *= audio.duration_ms / duration_ms
            return await _synthesize_step(rate, retries - 1)

    output_file, speech_rate = await _synthesize_step(
        rate=1.0, retries=SYNTHESIS_RETRIES
    )

    return output_file, Voice(speech_rate=speech_rate, character=voice, pitch=pitch)


async def synthesize_events(
    events: Sequence[Event],
    voice: Character,
    lang: str,
    pitch: float,
    output_dir: Path | str,
) -> Tuple[Path, Sequence[Voice]]:
    output_dir = Path(output_dir)
    current_time_ms = 0
    clips = []
    voices = []

    for event in events:
        padding_ms = event.time_ms - current_time_ms
        clip, voice_info = await synthesize_text(
            text=" ".join(event.chunks),
            duration_ms=event.duration_ms,
            voice=voice if event.voice is None else event.voice.character,
            lang=lang,
            pitch=pitch if event.voice is None else event.voice.pitch,
            output_dir=output_dir,
        )
        (audio, *_), _ = media.probe(clip)
        assert isinstance(audio, Audio)

        clips += [(padding_ms, clip)]
        current_time_ms = event.time_ms + audio.duration_ms

        voices += [voice_info]

    output_file = await media.concat_and_pad(clips, output_dir)

    return output_file, voices


def normalize_speech(
    events: Sequence[Event], gap_ms: int, length: int
) -> Sequence[Event]:
    """Transforms speech events into a fewer and longer ones
    representing continuous speech."""

    REMOVE_SYMBOLS = "\n"

    scrubbed_events = [
        replace(e, chunks=[remove_symbols(" ".join(e.chunks), REMOVE_SYMBOLS)])
        for e in events
    ]

    gaps = [
        e2.time_ms - e1.time_ms - e1.duration_ms
        for e1, e2 in zip(scrubbed_events[:-1], scrubbed_events[1:])
    ]

    def _concat_events(e1: Event, e2: Event) -> Event:
        shift_ms = e2.time_ms - e1.time_ms
        gap_sec = (shift_ms - e1.duration_ms) / 1000.0

        return Event(
            time_ms=e1.time_ms,
            duration_ms=shift_ms + e2.duration_ms,
            chunks=[
                f"{' '.join(e1.chunks)} #{gap_sec:.2f}# {' '.join(e2.chunks)}"  # noqa: E501
            ],
            voice=e2.voice,
        )

    first_event, *events = scrubbed_events
    acc = [first_event]

    for event, gap in zip(events, gaps):
        last_event = acc.pop()
        last_text = (" ".join(last_event.chunks)).strip()

        if gap > gap_ms:
            acc += [last_event, event]
        elif len(last_text) > length and (
            last_text.endswith(".")
            or last_text.endswith("!")
            or last_text.endswith("?")
        ):
            acc += [last_event, event]
        elif last_event.voice != event.voice:
            acc += [last_event, event]
        else:
            acc += [_concat_events(last_event, event)]

    return acc
