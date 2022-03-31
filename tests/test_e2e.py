from freespeech import language, speech
from freespeech.types import Transcript, Event


TEXT = [
    "One hen.\n\n",
    "Two ducks.\n\n",
    "Three squawking geese.\n\n",
    "Four limerick oysters.\n\n",
    "Five corpulent porpoises\n\n",
    "Six pairs of Don Alverzo's tweezers.\n\n",
    "Seven thousand Macedonians in full battle array.\n\n",
    "Eight brass monkeys from the ancient sacred crypts of Egypt.\n\n",
    "Nine apathetic, sympathetic, diabetic old men on roller skates, "
    "with a marked propensity towards procrastination and sloth."""
]


def test_e2e():
    transcript = language.translate(
        text=Transcript(
            lang="en-US",
            events=[Event(
                time_ms=0,
                duration_ms=30_000,
                chunks=TEXT
            )]
        ),
        source=None,
        target="ru-RU"
    )

    audio = speech.synthesize(
        transcript=transcript,
        voice="ru-RU-WaveNet-A",
        storage_url="gs://freespeech-tests/e2e/"
    )

    assert abs(audio.duration_ms - 30_000) < 500
