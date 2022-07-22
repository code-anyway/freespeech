import os
import time

from freespeech.lib import transcript
from freespeech.types import Event, Settings, Source, Transcript, Voice

EXPECTED_EVENTS = [
    Event(
        time_ms=0,
        duration_ms=1000,
        chunks=["Hello, Bill!", "How are you?"],
        voice=Voice(character="Grace Hopper", pitch=0.0, speech_rate=1.0),
    ),
    Event(
        time_ms=2000,
        chunks=["It was a huge mistake."],
        voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.4),
    ),
]
EXPECTED_TRANSCRIPT = Transcript(
    title=None,
    lang="en-US",
    source=Source(method="Subtitles", url="https://youtube.com/foo"),
    settings=Settings(),
    events=EXPECTED_EVENTS,
)
EXPECTED_TEXT = """origin: https://youtube.com/foo
language: en-US
voice: Alonzo Church
clip_id: deadbeef239
method: Subtitles
original_audio_level: 2
video:

00:00:00.000000/00:00:01.000000 (Grace Hopper)
Hello, Bill!
How are you?

00:00:02.000000@1.40
It was a huge mistake.
"""


def test_unparse_time_interval():
    up = transcript.unparse_time_interval
    # assert up(0, 1000, Voice(character="Grace Hopper")) \
    #        == "00:00:00/00:00:01 (Grace Hopper)"

    # and this should work well regardless of what timezone is set
    current_tz = os.environ.get("TZ", None)
    try:
        os.environ["TZ"] = "America/Los_Angeles"
        time.tzset()
        assert (
            up(0, 1000, Voice(character="Grace Hopper"))
            == "00:00:00.000000/00:00:01.000000 (Grace Hopper)"
        )
    finally:
        # cleaning up the timezone
        if current_tz:
            os.environ["TZ"] = current_tz
        else:
            del os.environ["TZ"]
        time.tzset()


def test_parse_event():
    parse = transcript.parse_time_interval

    assert parse("00:00:00.000/00:00:00.000") == (0, 0, None, None)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0, None, None)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119, None, None)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119, None, None)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122, None, None)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0, None, None)
    assert parse("00:00:00.000/00:00:00.000 (Alonzo Church)") == (
        0,
        0,
        "Alonzo Church",
        None,
    )
    assert parse("00:00:00.000#0 (Alonzo Church)") == (0, 0, "Alonzo Church", None)
    assert parse("00:00:00.000#0.0 (Alonzo Church)") == (0, 0, "Alonzo Church", None)
    assert parse("00:00:00.001#0.1") == (1, 100, None, None)


def test_parse_time_interval():
    correct_intervals = [
        "00:13:00.50000/00:13:00.50000",
        "00:13:00.500/00:13:00.500",
        "  00:13:00.500000  / 00:13:00.500000   ",
        "00:13:00.5/00:13:00.5",
        "00:13:00.50/00:13:00.50",
        "00:13:00.500/00:13:00.500",
        "00:13:00.5000/00:13:00.5000",
        "00:13:00.50000/00:13:00.50000",
        "00:13:00.500000/00:13:00.500000",
        "00:13:00.500000/00:13:00.5000000000000",
        "00:13:00.5000/00:13:00.5000",
    ]
    correct_parsed = (13 * 60 * 1000 + 500, 0, None, None)

    for sample in correct_intervals:
        assert transcript.parse_time_interval(sample) == correct_parsed

    # case for no dots
    assert transcript.parse_time_interval("00:13:00/00:13:00") == (
        13 * 60 * 1000,
        0,
        None,
        None,
    )

    # case for single digit
    assert transcript.parse_time_interval("00:1:00/00:1:00") == (
        1 * 60 * 1000,
        0,
        None,
        None,
    )

    # case for real duraiton
    assert transcript.parse_time_interval("00:00:00/00:03:30") == (
        0,
        3.5 * 60 * 1000,
        None,
        None,
    )


def test_srt():
    files = [
        "tests/lib/data/transcript/karlsson.srt",
    ]

    for file in files:
        with open(file) as lines:
            text = "".join(lines)
            assert transcript.events_to_srt(transcript.srt_to_events(text)) == text


def test_parse():
    t = transcript.parse_transcript(EXPECTED_TEXT)
    assert t == EXPECTED_TRANSCRIPT


def test_parse_properties():
    text = "foo: bar\nboo: baz"
    assert transcript.parse_properties(text) == {"foo": "bar", "boo": "baz"}
