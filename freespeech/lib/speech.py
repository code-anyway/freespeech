import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple

import azure.cognitiveservices.speech as azure_tts
from deepgram import Deepgram
from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech as google_tts
from google.cloud.speech_v1.types.cloud_speech import LongRunningRecognizeResponse

from freespeech import env
from freespeech.lib import concurrency, media
from freespeech.lib.storage import obj
from freespeech.lib.text import (
    chunk,
    is_sentence,
    make_sentence,
    remove_symbols,
    split_sentences,
)
from freespeech.types import (
    Audio,
    Character,
    Event,
    Language,
    Literal,
    ServiceProvider,
    TranscriptionModel,
    Voice,
    assert_never,
    is_character,
    url,
)

logger = logging.getLogger(__name__)

Normalization = Literal["break_ends_sentence", "extract_breaks_from_sentence"]

MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit

# Let's give voices real names and map them to API-specific names
# https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support
# https://cloud.google.com/text-to-speech/docs/voices
VOICES: Dict[Character, Dict[Language, Tuple[ServiceProvider, str]]] = {
    "Ada Lovelace": {
        "en-US": ("Google", "en-US-Wavenet-F"),
        "ru-RU": ("Google", "ru-RU-Wavenet-E"),
        "pt-PT": ("Google", "pt-PT-Wavenet-D"),
        "de-DE": ("Google", "de-DE-Wavenet-C"),
        "es-US": ("Google", "es-US-Wavenet-A"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
    },
    "Grace Hopper": {
        "en-US": ("Google", "en-US-Wavenet-C"),
        "ru-RU": ("Google", "ru-RU-Wavenet-C"),
        "pt-PT": ("Google", "pt-PT-Wavenet-A"),
        "de-DE": ("Google", "de-DE-Wavenet-F"),
        "uk-UA": ("Google", "uk-UA-Wavenet-A"),
        "es-US": ("Google", "es-US-Wavenet-A"),
    },
    "Alan Turing": {
        "en-US": ("Google", "en-US-Wavenet-I"),
        "ru-RU": ("Google", "ru-RU-Wavenet-D"),
        "pt-PT": ("Google", "pt-PT-Wavenet-C"),
        "de-DE": ("Google", "de-DE-Wavenet-B"),
        "es-US": ("Google", "es-US-Wavenet-B"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
    },
    "Alonzo Church": {
        "en-US": ("Google", "en-US-Wavenet-D"),
        "ru-RU": ("Google", "ru-RU-Wavenet-B"),
        "pt-PT": ("Google", "pt-PT-Wavenet-B"),
        "de-DE": ("Google", "de-DE-Wavenet-D"),
        "es-US": ("Google", "es-US-Wavenet-C"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
    },
    "Bill": {
        "en-US": ("Azure", "en-US-ChristopherNeural"),
        "ru-RU": ("Azure", "ru-RU-DmitryNeural"),
        "pt-PT": ("Azure", "pt-PT-DuarteNeural"),
        "de-DE": ("Azure", "de-DE-ConradNeural"),
        "es-US": ("Azure", "es-US-AlonsoNeural"),
        "uk-UA": ("Azure", "uk-UA-OstapNeural"),
    },
    "Melinda": {
        "ru-RU": ("Azure", "ru-RU-DariyaNeural"),
        "en-US": ("Azure", "en-US-AriaNeural"),
        "pt-PT": ("Azure", "pt-PT-RaquelNeural"),
        "de-DE": ("Azure", "de-DE-KlarissaNeural"),
        "es-US": ("Azure", "es-US-PalomaNeural"),
        "uk-UA": ("Azure", "uk-UA-PolinaNeural"),
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
def supported_google_voices() -> Dict[str, Sequence[str]]:
    client = google_tts.TextToSpeechClient()

    # Performs the list voices request
    response = client.list_voices()

    return {voice.name: voice.language_codes for voice in response.voices}


@cache
def supported_azure_voices() -> Dict[str, Sequence[str]]:
    azure_key, azure_region = env.get_azure_config()
    config = azure_tts.SpeechConfig(subscription=azure_key, region=azure_region)
    ms_synthesizer = azure_tts.SpeechSynthesizer(config, None)
    all_languages = ms_synthesizer.get_voices_async().get()
    return {v.short_name: v.locale for v in all_languages.voices}


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
        case never:
            assert_never(never)


async def _transcribe_deepgram(
    uri: url, audio: Audio, lang: Language, model: TranscriptionModel
):
    # For more info see language section of
    # https://developers.deepgram.com/api-reference/#transcription-prerecorded
    LANGUAGE_OVERRIDE = {
        "uk-UA": "uk",
        "ru-RU": "ru",
        "de-DE": "de",
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

    return root.tag == "{http://www.w3.org/2001/10/synthesis}speak"


def _wrap_in_ssml(text: str, voice: str, speech_rate: float) -> str:
    text = "".join([f"<s>{sentence}</s>" for sentence in split_sentences(text)])

    result = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">'
        '<voice name="{VOICE}"><prosody rate="{RATE:f}">{TEXT}</prosody></voice>'
        "</speak>".format(TEXT=text, VOICE=voice, RATE=speech_rate)
    )
    assert is_valid_ssml(result), f"text={text} result={result}"
    return result


def text_to_chunks(text: str, chunk_length: int, voice: str) -> Sequence[str]:
    inner = re.sub(r"#(\d+(\.\d+)?)#", r'<break time="\1s" />', text)
    overhead = len(_wrap_in_ssml("", voice=voice, speech_rate=1.0))
    sentence_overhead = len("<s></s>")
    return chunk(
        text=inner,
        max_chars=chunk_length - overhead,
        sentence_overhead=sentence_overhead,
    )


async def synthesize_text(
    text: str,
    duration_ms: int,
    voice: Character,
    lang: Language,
    pitch: float,
    output_dir: Path | str,
) -> Tuple[Path, Voice]:
    if voice not in VOICES:
        raise ValueError(f"Unsupported voice: {voice}\n" f"Supported voices: {VOICES}")

    if lang not in VOICES[voice]:
        raise ValueError(f"Unsupported lang {lang} for {voice}\n")

    provider, provider_voice = VOICES[voice][lang]
    match provider:
        case "Google":
            all_voices = supported_google_voices()
        case "Azure":
            all_voices = supported_azure_voices()
        case "Deepgram":
            raise ValueError("Deepgram can not be used as TTS provider")
        case never:
            assert_never(never)

    chunks_with_breaks_expanded = text_to_chunks(
        text, chunk_length=MAX_CHUNK_LENGTH, voice=provider_voice
    )

    if provider_voice not in all_voices or lang not in all_voices[provider_voice]:
        raise ValueError(
            (
                f"{provider} Speech Synthesis API "
                "doesn't support {lang} for voice {voice}\n"
                f"Supported values: {all_voices}"
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

        def _google_api_call(ssml_phrase: str) -> bytes:
            client = google_tts.TextToSpeechClient()
            result = client.synthesize_speech(
                input=google_tts.SynthesisInput(ssml=ssml_phrase),
                voice=google_tts.VoiceSelectionParams(
                    language_code=lang,
                ),
                audio_config=google_tts.AudioConfig(
                    audio_encoding=google_tts.AudioEncoding.LINEAR16,
                    pitch=pitch,
                ),
            )
            return result.audio_content

        def _azure_api_call(ssml_phrase: str) -> bytes:
            azure_key, azure_region = env.get_azure_config()
            speech_config = azure_tts.SpeechConfig(
                subscription=azure_key, region=azure_region
            )
            speech_synthesizer = azure_tts.SpeechSynthesizer(
                speech_config=speech_config, audio_config=None
            )
            result = speech_synthesizer.speak_ssml(ssml_phrase)
            if not result.reason == azure_tts.ResultReason.SynthesizingAudioCompleted:
                logger.error(
                    f"Error synthesizing voice with Azure provider."
                    f" {result.reason}, {result.cancellation_details}"
                )
                raise RuntimeError(
                    f"Error synthesizing voice with Azure. {result.reason}"
                )

            return result.audio_data

        match provider:
            case "Azure":
                _api_call = _azure_api_call
            case "Google":
                _api_call = _google_api_call
            case "Deepgram":
                raise ValueError("Can not use Deepgram as a TTS provider")
            case never:
                assert_never(never)

        responses = await asyncio.gather(
            *[
                concurrency.run_in_thread_pool(
                    _api_call,
                    _wrap_in_ssml(phrase, voice=provider_voice, speech_rate=rate),
                )
                for phrase in chunks_with_breaks_expanded
            ]
        )

        with TemporaryDirectory() as tmp_dir:
            files = [f"{media.new_file(tmp_dir)}.wav" for _ in responses]
            for file, response in zip(files, responses):
                with open(file, "wb") as fd:
                    fd.write(response)
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
    lang: Language,
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


def concat_events(e1: Event, e2: Event, break_sentence: bool) -> Event:
    shift_ms = e2.time_ms - e1.time_ms
    gap_sec = (shift_ms - e1.duration_ms) / 1000.0

    if break_sentence:
        first = make_sentence(" ".join(e1.chunks))
        second = " ".join(e2.chunks).capitalize()
    else:
        first = " ".join(e1.chunks)
        second = " ".join(e2.chunks)

    return Event(
        time_ms=e1.time_ms,
        duration_ms=shift_ms + e2.duration_ms,
        chunks=[f"{first} #{gap_sec:.2f}# {second}"],
        voice=e2.voice,
    )


def normalize_speech(
    events: Sequence[Event], gap_ms: int, length: int, method: Normalization
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

    first_event, *events = scrubbed_events
    acc = [first_event]

    for event, gap in zip(events, gaps):
        last_event = acc.pop()
        last_text = (" ".join(last_event.chunks)).strip()

        if gap > gap_ms:
            acc += [last_event, event]
        elif len(last_text) > length and is_sentence(last_text):
            acc += [last_event, event]
        elif last_event.voice != event.voice:
            acc += [last_event, event]
        else:
            match method:
                case "break_ends_sentence":
                    acc += [concat_events(last_event, event, break_sentence=True)]
                case "extract_breaks_from_sentence":
                    raise NotImplementedError()
                case never:
                    assert_never(never)

    return acc
