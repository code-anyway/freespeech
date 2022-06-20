from freespeech.lib import transcript


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