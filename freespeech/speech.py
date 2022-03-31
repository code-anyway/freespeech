from typing import overload, List, Tuple
from tempfile import TemporaryDirectory
from freespeech import text, media
from freespeech.types import Audio, Event, Transcript, Voice, Language
from google.cloud import texttospeech

from google.cloud import speech as speech_api


MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit


GOOGLE_CLOUD_ENCODINGS = {
    "LINEAR16": speech_api.RecognitionConfig.AudioEncoding.LINEAR16,
    "WEBM_OPUS": speech_api.RecognitionConfig.AudioEncoding.WEBM_OPUS
}

SUPPORTED_VOICES = (
        *[f"en-US-Wavenet-{suffix}" for suffix in "ABCDEFGHIJ"],
        *[f"ru-RU-Wavenet-{suffix}" for suffix in "ABCDE"],
    )

SUPPORTED_LANGUAGES = ("en-US", "ru-RU")

SYNTHESIS_ERROR_MS = 10
SYNTHESIS_RETRIES = 10

TRANSCRIBE_TIMEOUT_SEC = 120


def transcribe(audio: Audio, model: str = "default") -> Transcript:
    if audio.lang is None:
        raise ValueError("audio.lang is not set.")

    if audio.encoding not in GOOGLE_CLOUD_ENCODINGS:
        raise ValueError(
            ("Invalid audio.encoding. "
             f"Expcected values {','.join(GOOGLE_CLOUD_ENCODINGS)}."))

    if audio.num_channels != 1:
        raise ValueError((
            "Audio should be mono for best results. "
            "Set audio.num_channels to 1."
        ))

    client = speech_api.SpeechClient()
    operation = client.long_running_recognize(
        config=speech_api.RecognitionConfig(
            audio_channel_count=audio.num_channels,
            encoding=GOOGLE_CLOUD_ENCODINGS[audio.encoding],
            sample_rate_hertz=audio.sample_rate_hz,
            language_code=audio.lang,
            model=model,
            # metadata=speech_api.RecognitionMetadata(
            #     recording_device_type=speech_api.RecognitionMetadata.RecordingDeviceType.SMARTPHONE,  # noqa: E501
            #     original_media_type=speech_api.RecognitionMetadata.OriginalMediaType.VIDEO,  # noqa: E501
            # )
        ),
        audio=speech_api.RecognitionAudio(uri=audio.url)
    )
    response = operation.result(timeout=TRANSCRIBE_TIMEOUT_SEC)

    current_time_ms = 0
    events = []

    for result in response.results:
        result_end_time_ms = int(result.result_end_time.total_seconds() * 1000)
        event = Event(
            time_ms=current_time_ms,
            duration_ms=result_end_time_ms - current_time_ms,
            chunks=[result.alternatives[0].transcript]
        )
        current_time_ms = result_end_time_ms
        events += [event]

    return Transcript(
        lang=audio.lang,
        events=events
    )


def _synthesize(
    transcript: str,
    duration_ms: int,
    voice: Voice,
    lang: Language,
    storage_url: str,
    pitch: float = 0.0,
) -> Audio:
    chunks = text.chunk(transcript, MAX_CHUNK_LENGTH)

    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError((
            f"Unsupported language: {lang}. "
            f"Supported languages: {SUPPORTED_LANGUAGES}"))

    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError((
            f"Unsupported voice: {lang}. "
            f"Supported voices: {SUPPORTED_VOICES}"))

    client = texttospeech.TextToSpeechClient()

    def _synthesize(speaking_rate: float) -> Audio:
        responses = [
            client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=phrase),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=lang, name=voice
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    pitch=pitch,
                    speaking_rate=speaking_rate,
                ),
            )
            for phrase in chunks
        ]

        with TemporaryDirectory() as tmp_dir:
            clips = []
            for i, response in enumerate(responses):
                tmp_filename = f"{tmp_dir}/response-{i}.wav"
                with open(tmp_filename, "wb") as fd:
                    fd.write(response.audio_content)
                clip, = media.probe(f"file://{tmp_filename}")
                assert isinstance(clip, Audio)
                clips += [clip]
            return media.concat(
                [(0, clip) for clip in clips],
                storage_url=storage_url)

    # Iteratively adjust speaking rate
    speaking_rate = 1.0
    for _ in range(SYNTHESIS_RETRIES):
        audio = _synthesize(speaking_rate)
        if abs(audio.duration_ms - duration_ms) < SYNTHESIS_ERROR_MS:
            audio.voice = voice
            audio.lang = lang
            return audio
        speaking_rate *= (audio.duration_ms / duration_ms)

    raise RuntimeError((
        "Unable to converge while adjusting speaking_rate "
        f"after {SYNTHESIS_RETRIES} attempts.")
    )


def synthesize(
    transcript: Transcript,
    voice: Voice,
    storage_url: str,
    pitch: float = 0.0
) -> Audio:
    clips: List[Tuple[int, Audio]] = []
    current_time_ms = 0

    with TemporaryDirectory() as tmp_dir:
        for event in transcript.events:
            padding_ms = event.time_ms - current_time_ms
            clip = _synthesize(
                transcript="".join(event.chunks),
                duration_ms=event.duration_ms,
                voice=voice,
                lang=transcript.lang,
                storage_url=f"file://{tmp_dir}",
                pitch=pitch,
            )

            clips += [(padding_ms, clip)]
            current_time_ms = event.time_ms + clip.duration_ms

        return media.concat(clips, storage_url)
