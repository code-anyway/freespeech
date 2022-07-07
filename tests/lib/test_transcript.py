import os
import time

from freespeech.lib import transcript
from freespeech.types import Event, Voice


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
            == "00:00:00/00:00:01 (Grace Hopper)"
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

    assert parse("00:00:00.000/00:00:00.000") == (0, 0, None)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0, None)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119, None)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119, None)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122, None)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0, None)
    assert parse("00:00:00.000/00:00:00.000 (Alonzo Church)") == (0, 0, "Alonzo Church")
    assert parse("00:00:00.000#0 (Alonzo Church)") == (0, 0, "Alonzo Church")
    assert parse("00:00:00.000#0.0 (Alonzo Church)") == (0, 0, "Alonzo Church")
    assert parse("00:00:00.001#0.1") == (1, 100, None)


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
    correct_parsed = (13 * 60 * 1000 + 500, 0, None)

    for sample in correct_intervals:
        assert transcript.parse_time_interval(sample) == correct_parsed

    # case for no dots
    assert transcript.parse_time_interval("00:13:00/00:13:00") == (
        13 * 60 * 1000,
        0,
        None,
    )

    # case for single digit
    assert transcript.parse_time_interval("00:1:00/00:1:00") == (1 * 60 * 1000, 0, None)

    # case for real duraiton
    assert transcript.parse_time_interval("00:00:00/00:03:30") == (
        0,
        3.5 * 60 * 1000,
        None,
    )


def test_srt():
    SRT_FILE = "tests/lib/data/transcript/karlsson.srt"

    with open(SRT_FILE) as lines:
        res = transcript.parse_srt("".join(lines))

    expected = [
        Event(
            time_ms=8484,
            duration_ms=5205,
            chunks=["Inspired by Astrid Lindgren's fairy tale."],
            voice=None,
        ),
        Event(
            time_ms=15383, duration_ms=4373, chunks=["Karlsson and The Kid"], voice=None
        ),
    ]
    assert res == expected
