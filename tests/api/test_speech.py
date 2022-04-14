from freespeech.api import media, speech
from freespeech.api.storage import obj
from freespeech.types import Event

AUDIO_EN_LOCAL = "tests/api/data/media/en-US-mono.wav"
AUDIO_EN_GS = "gs://freespeech-tests/test_speech/en-US-mono.wav"

TEST_OUTPUT_GS = "gs://freespeech-tests/test_speech/output/"


def test_transcribe():
    obj.put(AUDIO_EN_LOCAL, AUDIO_EN_GS)
    (audio, *_), _ = media.probe(AUDIO_EN_LOCAL)
    assert not _

    t_en = speech.transcribe(AUDIO_EN_GS, audio, "en-US", model="default")

    event = Event(time_ms=0, duration_ms=3230, chunks=['1 2 3'])
    assert t_en == [event]


def test_synthesize_text(tmp_path):
    output = speech.synthesize_text(
        text="One. Two. Three.",
        duration_ms=4_000,
        voice="Grace Hopper",
        lang="en-US",
        pitch=1.0,
        output_dir=tmp_path,
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 4_000) < eps

    output_gs = obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")

    (t_en, *tail) = speech.transcribe(
        output_gs,
        audio,
        "en-US",
        model="default")
    assert not tail, f"Extra events returned from transcribe: {tail}"
    assert t_en.chunks == ["1 2 3"]


def test_synthesize_events(tmp_path):
    events = [
        Event(
            time_ms=1_000,
            duration_ms=2_000,
            chunks=["One hen.", "Two ducks."]
        ),
        Event(
            time_ms=5_000,
            duration_ms=2_000,
            chunks=["Three squawking geese."]
        ),
    ]

    output = speech.synthesize_events(
        events=events,
        voice="Alan Turing",
        lang="en-US",
        pitch=1.0,
        output_dir=tmp_path
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 7000) < eps

    output_gs = obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")

    t_en = speech.transcribe(
        output_gs,
        audio,
        "en-US",
        model="default")

    assert t_en == [
        Event(
            time_ms=0,
            duration_ms=3030,
            chunks=['one hen two ducks']),
        Event(
            time_ms=3030,
            duration_ms=3940,
            chunks=[' three squawking geese'])
    ]
