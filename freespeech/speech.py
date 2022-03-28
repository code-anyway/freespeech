from freespeech import text
from freespeech.types import Audio, Transcript, Language, Voice


MAX_CHUNK_LENGTH = 1000  # Google Speech API Limit


def synthesize(
    text: Transcript,
    language: Language,
    voice: Voice,
) -> Audio:

    # speaking_rate: float,
    # pitch: float,
    # output_path: str,

    phrases = text.chunk(text, MAX_CHUNK_LENGTH)

    assert language_code in ("en-US", "ru-RU")
    assert voice_name in (
        *[f"en-US-Wavenet-{suffix}" for suffix in "ABCDEFGHIJ"],
        *[f"ru-RU-Wavenet-{suffix}" for suffix in "ABCDE"],
    )

    client = texttospeech.TextToSpeechClient()

    responses = [
        client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=phrase),
            voice=texttospeech.VoiceSelectionParams(
                language_code=language, name=voice
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                pitch=pitch,
                speaking_rate=speaking_rate,
            ),
        )
        for phrase in phrases
    ]

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
