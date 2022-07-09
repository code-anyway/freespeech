import pytest

from freespeech.lib import gdocs, transcript
from freespeech.types import Event, Voice

EXPECTED_PAGE = transcript.Page(
    origin="https://youtube.com/foo",
    language="en-US",
    voice="Alonzo Church",
    clip_id="deadbeef239",
    method="Subtitles",
    original_audio_level=2,
    video=None,
)
EXPECTED_EVENTS = [
    Event(
        time_ms=0,
        duration_ms=1000,
        chunks=["Hello, Bill!", "How are you?"],
        voice=Voice(character="Grace Hopper", pitch=0.0, speech_rate=1.0),
    ),
    Event(
        time_ms=2000,
        duration_ms=None,
        chunks=["It was a huge mistake."],
        voice=Voice(character="Alonzo Church", pitch=0.0, speech_rate=1.4),
    ),
]
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

00:00:02.000000/00:00:04.000000
It was a huge mistake.
"""


def test_extract():
    correct_url = (
        "https://docs.google.com/document/d/"
        "1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit"
    )
    res = gdocs.extract(correct_url)
    assert res == "Hello World\n\nNew Paragraph\n"

    with pytest.raises(RuntimeError, match=r"Requested entity was not found."):
        gdocs.extract("https://docs.google.com/document/d/INVALID_ID/edit")

    with pytest.raises(PermissionError, match=r"The caller does not have permission"):
        no_perm = (
            "https://docs.google.com/document/d/"
            "1kfP8KZo4wKfPrFWDfdbMJvvGR6ZBzHgcOMu-DAgstuc/edit"
        )
        gdocs.extract(no_perm)

    with pytest.raises(ValueError, match=r"Invalid URL: .*"):
        gdocs.extract("https://docs.google.com/INVALID_GDOCS_URL")


def test_parse():
    parsed_page = gdocs.parse_properties(
        """origin: https://youtube.com/foo
        language: en-US
        voice: Alonzo Church
        clip_id: deadbeef239
        apple banana: orange
        method: Subtitles
        original_audio_level: 2
        video:
        """
    )
    assert parsed_page == EXPECTED_PAGE
    with pytest.raises(AttributeError, match=".*(?=must be defined)"):
        gdocs.parse_properties("") == EXPECTED_PAGE


def test_extract_and_parse():
    url = "https://docs.google.com/document/d/1wZQoh-8hlBRBJylhAkNSGAefLvQ5kqYGg2O-nW8tq_k"  # noqa: E501
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


def test_long_transcript():
    url = "https://docs.google.com/document/d/1FQEWOvJPq3_KR7pm2-L_GWqHgKRP9iq0Cx1vwNGCptg/edit#"  # noqa: E501
    page, events = gdocs.parse(gdocs.extract(url))

    assert page.origin == "https://www.youtube.com/watch?v=U93QRMcQU5Y"
    assert len(events) == 14
