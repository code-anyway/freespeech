import json
import pytest


from freespeech.notion import client
from freespeech.types import Transcript, Event


TEST_PAGE_ID = "fe999aa7a53a448a8b6f3dcfe07ab434"
TEST_DATABASE_ID = "4d8d51229d854929b193a13604bf47dc"
TEST_PAGE_ID_ID_FOR_UPDATES = "553e3db2376341a7ae8abd4faa93131d"

EVENTS_EN = [
    Event(
        time_ms=1001,
        duration_ms=2001,
        chunks=["One hen. Two ducks."]
    ),
    Event(
        time_ms=4001,
        duration_ms=2001,
        chunks=["Three squawking geese."]
    )
]

EVENTS_RU = [
    Event(
        time_ms=1001,
        duration_ms=2001,
        chunks=["Одна курица. Две утки."]
    ),
    Event(
        time_ms=4001,
        duration_ms=2001,
        chunks=["Два кричащих гуся."]
    )
]


def test_get_all_pages():
    expected = [
        "553e3db2-3763-41a7-ae8a-bd4faa93131d",
        "8b4fcdb2-e90a-4a2b-951d-af46992d893a",
        "fe999aa7-a53a-448a-8b6f-3dcfe07ab434"
    ]

    pages = client.get_pages(TEST_DATABASE_ID, page_size=2)
    assert set(pages) == set(expected)


def test_get_pages_by_property():
    assert client.get_pages(TEST_DATABASE_ID, stage="Transcribe") == ["uuid2"]
    with pytest.raises(AttributeError, match=r"Invalid property: foo"):
        client.get_pages(TEST_DATABASE_ID, foo="bar")


def test_get_page():
    doc = client.get_page(TEST_PAGE_ID)
    assert doc.title == "Announcer's test"


def test_parse_event():
    parse = client._parse_event

    assert parse("00:00:00.000/00:00:00.000") == (0, 0)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0)
    assert parse("00:00:00.001/00:00:00.120") == (1, 120)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 2120)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 80123)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 3661123)


def test_parse_transcript_from_test_data():
    with open("tests/data/transcript_block.json") as fd:
        block = json.load(fd)
        transcript = client.parse_transcript(block, lang="en-US")

    assert transcript == Transcript(
        _id=transcript._id,
        lang="en-US",
        events=EVENTS_EN
    )


def test_get_transcripts_from_notion():
    en_EN, ru_RU = client.get_transcripts(TEST_PAGE_ID)
    assert en_EN == Transcript(
        _id=en_EN._id,
        lang="en-EN",
        events=EVENTS_EN
    )
    assert ru_RU == Transcript(
        _id=ru_RU._id,
        lang="ru-RU",
        events=EVENTS_RU
    )


def test_create_child_document():
    pass


def test_put_transcript():
    new_transcript = Transcript(
        lang="uk-UK",
        events=[
            Event(
                time_ms=60000,
                duration_ms=5000,
                chunks=["Путiн хуiло."]
            )
        ]
    )

    client.add_transcript(TEST_PAGE_ID, new_transcript)
