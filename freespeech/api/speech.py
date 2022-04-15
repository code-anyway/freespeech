from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Tuple

from google.api_core import exceptions as google_api_exceptions
from google.cloud import speech as speech_api
from google.cloud import texttospeech

from freespeech.api import media
from freespeech.api.text import chunk
from freespeech.types import Audio, Character, Event, Voice

MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit

# Let's give voices real names and map them to API-specific names
VOICES = {
    "Grace Hopper": {
        "en-US": "en-US-Wavenet-C",
        "ru-RU": "ru-RU-Wavenet-C",
    },
    "Alan Turing": {
        "en-US": "en-US-Wavenet-I",
        "ru-RU": "ru-RU-Wavenet-D",
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
TRANSCRIBE_TIMEOUT_SEC = 120


@cache
def supported_voices() -> Dict[str, Sequence[str]]:
    client = texttospeech.TextToSpeechClient()

    # Performs the list voices request
    response = client.list_voices()

    return {voice.name: voice.language_codes for voice in response.voices}


def transcribe(
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
        operation = client.long_running_recognize(
            config=speech_api.RecognitionConfig(
                audio_channel_count=audio.num_channels,
                encoding=GOOGLE_CLOUD_ENCODINGS[audio.encoding],
                sample_rate_hertz=audio.sample_rate_hz,
                language_code=lang,
                model=model,
                # TODO (astaff): are there any measurable gains
                # from adjusting the hyper parameters?
                # metadata=speech_api.RecognitionMetadata(
                #     recording_device_type=speech_api.RecognitionMetadata.RecordingDeviceType.SMARTPHONE,  # noqa: E501
                #     original_media_type=speech_api.RecognitionMetadata.OriginalMediaType.VIDEO,  # noqa: E501
                # )
            ),
            audio=speech_api.RecognitionAudio(uri=uri),
        )
        response = operation.result(timeout=TRANSCRIBE_TIMEOUT_SEC)
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


def synthesize_text(
    text: str,
    duration_ms: int,
    voice: Character,
    lang: str,
    pitch: float,
    output_dir: media.path,
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

    client = texttospeech.TextToSpeechClient()

    def _synthesize_step(rate, retries) -> Tuple[Path, float]:
        if retries < 0:
            raise RuntimeError(
                (
                    "Unable to converge while adjusting speaking_rate "
                    f"after {SYNTHESIS_RETRIES} attempts."
                )
            )

        responses = [
            client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=phrase),
                voice=texttospeech.VoiceSelectionParams(language_code=lang, name=voice),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    pitch=pitch,
                    speaking_rate=rate,
                ),
            )
            for phrase in chunks
        ]

        with TemporaryDirectory() as tmp_dir:
            files = [f"{media.new_file(tmp_dir)}.wav" for _ in responses]
            for file, response in zip(files, responses):
                with open(file, "wb") as fd:
                    fd.write(response.audio_content)
            audio_file = media.concat(files, output_dir)

        (audio, *_), _ = media.probe(audio_file)
        assert isinstance(audio, Audio)

        if abs(audio.duration_ms - duration_ms) < SYNTHESIS_ERROR_MS:
            return Path(audio_file), rate
        else:
            rate *= audio.duration_ms / duration_ms
            return _synthesize_step(rate, retries - 1)

    output_file, speech_rate = _synthesize_step(rate=1.0, retries=SYNTHESIS_RETRIES)

    return output_file, Voice(speech_rate=speech_rate, character=voice, pitch=pitch)


def synthesize_events(
    events: Sequence[Event], voice: Character, lang: str, pitch: float, output_dir: media.path
) -> Tuple[Path, Sequence[Voice]]:
    current_time_ms = 0
    clips = []
    voices = []

    for event in events:
        padding_ms = event.time_ms - current_time_ms
        clip, voice_info = synthesize_text(text="".join(event.chunks),
                                           duration_ms=event.duration_ms,
                                           voice=voice,
                                           lang=lang,
                                           pitch=pitch,
                                           output_dir=output_dir)
        (audio, *_), _ = media.probe(clip)
        assert isinstance(audio, Audio)

        clips += [(padding_ms, clip)]
        current_time_ms = event.time_ms + audio.duration_ms

        voices += [voice_info]

    output_file = media.concat_and_pad(clips, output_dir)

    return output_file, voices
