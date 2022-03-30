from freespeech import speech
from freespeech.types import Audio


SPEECH_STORAGE_URL = "gs://freespeech-tests/streams/"
SPEECH_ID = "6a861e2e-1e44-450f-ab26-d4dabd8c5847"
SPEECH_SUFFIX = "webm"


def test_transcribe():
    audio = Audio(
        duration_ms=30_000,
        storage_url=SPEECH_STORAGE_URL,
        suffix=SPEECH_SUFFIX,
        _id=SPEECH_ID,
        encoding="WEBM_OPUS",
        sample_rate_hz=48_000,
        num_channels=1,
        lang="en-US"
    )
    t = speech.transcribe(audio, model="default")

    flat_transcript_text = "".join(sum([e.chunks for e in t.events], []))

    assert t.lang == "en-US"
    assert t.events == []
    assert flat_transcript_text == "One hen."
