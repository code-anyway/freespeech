import pytest

from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Event

AUDIO_EN_LOCAL = "tests/lib/data/media/en-US-mono.wav"
AUDIO_EN_GS = "gs://freespeech-tests/test_speech/en-US-mono.wav"

TEST_OUTPUT_GS = "gs://freespeech-tests/test_speech/output/"


@pytest.mark.asyncio
async def test_transcribe():
    await obj.put(AUDIO_EN_LOCAL, AUDIO_EN_GS)
    (audio, *_), _ = media.probe(AUDIO_EN_LOCAL)
    assert not _

    t_en = await speech.transcribe(AUDIO_EN_GS, audio, "en-US", model="default")

    event = Event(time_ms=0, duration_ms=3230, chunks=["1 2 3"])
    assert t_en == [event]


@pytest.mark.asyncio
async def test_synthesize_text(tmp_path):
    output, voice = await speech.synthesize_text(
        text="One. Two. Three.",
        duration_ms=4_000,
        voice="Grace Hopper",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 4_000) < eps

    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")

    (t_en, *tail) = await speech.transcribe(output_gs, audio, "en-US", model="default")
    assert not tail, f"Extra events returned from transcribe: {tail}"
    assert t_en.chunks == ["1 2 3"]
    assert voice.speech_rate == 0.45375
    assert voice.character == "Grace Hopper"
    assert voice.pitch == 0.0


@pytest.mark.asyncio
async def test_synthesize_events(tmp_path):
    events = [
        Event(time_ms=1_000, duration_ms=2_000, chunks=["One hen.", "Two ducks."]),
        Event(time_ms=5_000, duration_ms=2_000, chunks=["Three squawking geese."]),
    ]

    output, voices = await speech.synthesize_events(
        events=events, voice="Alan Turing", lang="en-US", pitch=0.0, output_dir=tmp_path
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 7000) < eps

    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")

    t_en = await speech.transcribe(output_gs, audio, "en-US", model="default")

    assert t_en == [
        Event(time_ms=0, duration_ms=3120, chunks=["one hen two ducks"]),
        Event(time_ms=3120, duration_ms=3820, chunks=[" three squawking geese"]),
    ]

    voice_1, voice_2 = voices

    assert voice_1.speech_rate == 0.9185
    assert voice_1.character == "Alan Turing"
    assert voice_1.pitch == 0.0

    assert voice_2.speech_rate == 0.7235
    assert voice_2.character == "Alan Turing"
    assert voice_2.pitch == 0.0


def test_normalize_speech():
    raise NotImplementedError()
