from freespeech.api import speech
from freespeech.types import Audio, Transcript, Event


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

    assert t.lang == "en-US"
    assert t.events == [Event(
        time_ms=0,
        duration_ms=28_840,
        chunks=[
            'one hen two ducks three squawking geese four Limerick oysters '
            'five corpulent porpoises six pair of Donald versus tweezers '
            '7000 do Indians in full battle array 8 brass monkeys from the '
            'Asian secret Crypts of Egypt nine apathetic sympathetic '
            'diabetic old men on roller skates with the marked propensity '
            'towards procrastination and sloth'
        ])
    ]


def test_synthesize_from_str(tmp_path):
    audio = speech._synthesize(
        transcript="One hen. Two ducks. Three squawking geese.",
        duration_ms=4_000,
        voice="en-US-Wavenet-A",
        lang="en-US",
        storage_url="gs://freespeech-tests/tests/"
    )

    assert audio.duration_ms == 3991
    t = speech.transcribe(audio, model="default")
    assert t.events[0].chunks[0] == "one hen two ducks three squawking geese"


def test_synthesize_from_transcript(tmp_path):
    transcript = Transcript(
        lang="en-US",
        events=[
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
    )
    audio = speech.synthesize(
        transcript=transcript,
        voice="en-US-Wavenet-A",
        storage_url="gs://freespeech-tests/tests/"
    )

    eps = 5
    assert abs(audio.duration_ms - 7000) < eps
    t = speech.transcribe(audio, model="default")
    assert t == Transcript(
        _id=t._id,
        lang="en-US",
        events=[
            Event(
                time_ms=0,
                duration_ms=3180,
                chunks=['one hen two ducks']),
            Event(
                time_ms=3180,
                duration_ms=3780,
                chunks=[' three squawking geese'])]
    )
