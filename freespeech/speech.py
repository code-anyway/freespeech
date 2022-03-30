from freespeech import text
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
    response = client.recognize(
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

    events = [
        Event(
            time_ms=0,
            duration_ms=30_000,
            chunks=[result.alternatives[0].transcript]
        )
        for result in response.results
    ]

    return Transcript(
        lang=audio.lang,
        events=events
    )


def synthesize(
    transcript: str,
    duration_ms: int,
    voice: Voice,
    lang: Language,
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
                    pitch=0.0,
                    speaking_rate=speaking_rate,
                ),
            ).audio_content
            for phrase in chunks
        ]


def synthesize(
    transcript: Transcript,
    voice: Voice,
) -> Audio:

    clips = [
        (
            event.time_ms,
            synthesize(
                transcript="".join(event.chunks),
                duration_ms=event.duration_ms,
                voice=voice,
                lang=transcript.lang,
            )
        )
        for event in transcript.events
    ]

    # speaking_rate: float,
    # pitch: float,
    # output_path: str,



    with tempfile.TemporaryDirectory() as media_root:
        inputs = []

        # astaff (20220311): refactor to use in-memory stream instead of a disk file
        for i, response in enumerate(responses):
            file_name = str(Path(media_root) / f"{hash(text)}-{i}.wav")

            with open(file_name, "wb") as out:
                out.write(response.audio_content)

            inputs += [ffmpeg.input(file_name).audio]

        # astaff (20220311): not specifying v and a gives a weird error
        # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
        stream = ffmpeg.concat(*inputs, v=0, a=1)

        ffmpeg.output(stream, output_path).run(
            overwrite_output=True, capture_stderr=True
        )
