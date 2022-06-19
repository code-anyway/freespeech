import pytest
from googleapiclient import errors

from freespeech.lib import gdocs
from freespeech.types import Event

EXPECTED_PAGE = gdocs.Page(
    origin="https://youtube.com/foo",
    language="en-US",
    voice="Alonzo Church",
    method="Subtitles",
    clip_id="deadbeef239",
    original_audio_level=2,
    video=None,
)
EXPECTED_EVENTS = [
    Event(time_ms=0, duration_ms=1000, chunks=["\nHello, Bill!\n\n"], voice=None),
    Event(
        time_ms=2000,
        duration_ms=2000,
        chunks=["\nIt was a huge mistake.\n"],
        voice=None,
    ),
]


def test_extract():
    res = gdocs.extract(
        "https://docs.google.com/document/d/1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit"  # noqa: E501
    )
    assert res == "Hello World\n\nNew Paragraph\n"

    with pytest.raises(errors.HttpError, match=r"HttpError 404 .+"):
        gdocs.extract("https://docs.google.com/document/d/INVALID_ID/edit")

    with pytest.raises(ValueError, match=r"Invalid URL: .*"):
        gdocs.extract("https://docs.google.com/INVALID_GDOCS_URL")


def test_read_transcript():
    url = "https://docs.google.com/document/d/16E56VsclHUOapBhcfEf9BzmN2pZklXZE1V1Oik2vSkM/edit?usp=sharing"
    page, events = gdocs.parse(gdocs.extract(url))

    # assert page == EXPECTED_PAGE
    assert events == EXPECTED_EVENTS
