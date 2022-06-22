import pytest
from googleapiclient import errors

from freespeech.lib import gdocs
from freespeech.types import Event, Voice

EXPECTED_PAGE = gdocs.Page(
    origin="https://youtube.com/foo",
    language="en-US",
    voice="Alonzo Church",
    clip_id="deadbeef239",
    method="Subtitles",
    original_audio_level=2.5,
    video=None,
)
EXPECTED_EVENTS = [
    Event(
        time_ms=0,
        duration_ms=1000,
        chunks=["Hello, Bill!", "How are you?"],
        voice=Voice(character="Grace Hopper", pitch=0.0, speech_rate=None),
    ),
    Event(
        time_ms=2000,
        duration_ms=2000,
        chunks=["It was a huge mistake."],
        voice=None,
    ),
]
EXPECTED_TEXT = """origin: https://youtube.com/foo
language: en-US
voice: Alonzo Church
clip_id: deadbeef239
method: Subtitles
original_audio_level: 2.5
video:

00:00:00/00:00:01 (Grace Hopper)
Hello, Bill!
How are you?

00:00:02/00:00:04
It was a huge mistake.
"""


def test_extract():
    res = gdocs.extract(
        "https://docs.google.com/document/d/1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit"  # noqa: E501
    )
    assert res == "Hello World\n\nNew Paragraph\n"

    with pytest.raises(errors.HttpError, match=r"HttpError 404 .+"):
        gdocs.extract("https://docs.google.com/document/d/INVALID_ID/edit")

    with pytest.raises(ValueError, match=r"Invalid URL: .*"):
        gdocs.extract("https://docs.google.com/INVALID_GDOCS_URL")


def test_parse():
    parsed_page = gdocs.parse_properties(
        """origin: https://youtube.com/foo
        language: en-US
        voice:      Alonzo Church
        clip_id: deadbeef239
        apple banana: orange
        method: Subtitles
        original_audio_level: 2.5
        video:
        """
    )
    assert parsed_page == EXPECTED_PAGE
    with pytest.raises(TypeError, match=".*(?=must be defined)"):
        gdocs.parse_properties("") == EXPECTED_PAGE


def test_extract_and_parse():
    url = "https://docs.google.com/document/d/16E56VsclHUOapBhcfEf9BzmN2pZklXZE1V1Oik2vSkM/edit?usp=sharing"  # noqa: E501
    page, events = gdocs.parse(gdocs.extract(url))

    assert page == EXPECTED_PAGE
    assert events == EXPECTED_EVENTS


def test_text_from_properties_and_events():
    loaded_text = gdocs.text_from_properties_and_events(EXPECTED_PAGE, EXPECTED_EVENTS)
    assert loaded_text == EXPECTED_TEXT


def test_create():
    url = gdocs.create("test_gdocs::test_create", EXPECTED_PAGE, EXPECTED_EVENTS)
    page, events = gdocs.parse(gdocs.extract(url))

    assert page == EXPECTED_PAGE
    assert events == EXPECTED_EVENTS
