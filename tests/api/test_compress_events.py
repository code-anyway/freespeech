from freespeech.api import transcript
from freespeech.typing import Event, Voice


def test_compress() -> None:
    events = [
        Event(
            time_ms=0,
            duration_ms=1000,
            chunks=["A"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=1000,
            duration_ms=1000,
            chunks=["B"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=2000,
            duration_ms=1000,
            chunks=["C"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
    ]

    compressed = transcript.compress(events, window_size_ms=0)
    assert compressed == events

    compressed = transcript.compress(events, window_size_ms=2000)
    assert compressed == [
        Event(
            time_ms=0,
            duration_ms=2000,
            chunks=["A B"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=2000,
            duration_ms=1000,
            chunks=["C"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
    ]

    compressed = transcript.compress(events, window_size_ms=4000)
    assert compressed == [
        Event(
            time_ms=0,
            duration_ms=3000,
            chunks=["A B C"],
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
    ]
