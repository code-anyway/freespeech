import asyncio
import logging
import statistics
from dataclasses import replace
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple

from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech

from freespeech.lib import concurrency, media
from freespeech.lib.text import chunk, remove_symbols
from freespeech.types import Audio, Character, Event, Voice

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
SYNTHESIS_ERROR_MS = 100

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
    uri: str, audio: Audio, lang: str, model: str = "default"
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

    if lang is None:
        raise ValueError(
            "Unable to determine language: audio.lang and lang are not set."
        )

    if audio.encoding not in GOOGLE_CLOUD_ENCODINGS:
        raise ValueError(
            (
                f"Invalid audio encoding: {audio.encoding} "
                f"Expected values {','.join(GOOGLE_CLOUD_ENCODINGS)}."
            )
        )

    if audio.num_channels != 1:
        raise ValueError(
            ("Audio should be mono for best results. " "Set audio.num_channels to 1.")
        )

    client = speech_api.SpeechClient()

    try:

        def _api_call():
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
            return operation.result(timeout=TRANSCRIBE_TIMEOUT_SEC)

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


async def synthesize_text(
    text: str,
    duration_ms: int,
    voice: Character,
    lang: str,
    pitch: float,
    output_dir: Path | str,
) -> Tuple[Path, Voice]:
    chunks = chunk(text, MAX_CHUNK_LENGTH)

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

    async def _synthesize_step(rate, retries) -> Tuple[Path, float]:
        if retries < 0:
            raise RuntimeError(
                (
                    "Unable to converge while adjusting speaking rate "
                    f"after {SYNTHESIS_RETRIES} attempts."
                    f"text={text} duration={duration_ms}"
                )
            )

        def _api_call(phrase):
            client = texttospeech.TextToSpeechClient()
            return client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=phrase),
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

        if abs(audio.duration_ms - duration_ms) < SYNTHESIS_ERROR_MS:
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


def _speech_rate(event: Event) -> float:
    return len(" ".join(event.chunks)) / event.duration_ms


def normalize_speech(
    events: Sequence[Event], gap_threshold: float = 300
) -> Sequence[Event]:
    """Transforms speech events into a fewer and longer ones
    representing continuous speech."""

    REMOVE_SYMBOLS = "\n"

    scrubbed_events = [
        replace(e, chunks=[remove_symbols(" ".join(e.chunks), REMOVE_SYMBOLS)])
        for e in events
    ]
    adjusted_events = _adjust_duration(scrubbed_events)
    gaps = [
        e2.time_ms - e1.time_ms - e1.duration_ms
        for e1, e2 in zip(adjusted_events[:-1], adjusted_events[1:])
    ]

    def _concat_events(e1: Event, e2: Event) -> Event:
        return Event(
            time_ms=e1.time_ms,
            duration_ms=e2.time_ms - e1.time_ms + e2.duration_ms,
            chunks=[" ".join(e1.chunks + e2.chunks)],
        )

    first_event, *events = adjusted_events
    acc = [first_event]

    for event, gap in zip(events, gaps):
        last_event = acc.pop()
        if gap > gap_threshold:
            acc += [last_event, event]
        else:
            acc += [_concat_events(last_event, event)]

    return acc


def _adjust_duration(events: Sequence[Event]) -> Sequence[Event]:
    if not events:
        return events

    speech_rates = [_speech_rate(e) for e in events]

    if len(speech_rates) > 1:
        sigma = statistics.stdev(speech_rates)
        mean = statistics.mean(speech_rates)
    else:
        sigma = 0
        mean = speech_rates[0]

    durations = [
        event.duration_ms * (speech_rate / mean)
        if speech_rate < mean - sigma
        else event.duration_ms
        for event, speech_rate in zip(events, speech_rates)
    ]

    logger.debug(f"durations = {durations}")

    adjusted_events = [
        replace(event, duration_ms=duration)
        for duration, event in zip(durations, events)
    ]

    return adjusted_events
