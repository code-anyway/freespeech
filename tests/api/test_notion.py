import json
import uuid


from freespeech.api import notion
from freespeech.types import Event


TEST_PAGE_ID = "fe999aa7a53a448a8b6f3dcfe07ab434"
TEST_DATABASE_ID = "4d8d51229d854929b193a13604bf47dc"
TEST_PAGE_ID_ID_FOR_UPDATES = "553e3db2376341a7ae8abd4faa93131d"

EVENTS_EN = [
    Event(
        time_ms=1001,
        duration_ms=1000,
        chunks=["One hen. Two ducks."]
    ),
    Event(
        time_ms=4001,
        duration_ms=2000,
        chunks=["Three squawking geese."]
    )
]

EVENTS_RU = [
    Event(
        time_ms=1001,
        duration_ms=1000,
        chunks=["Одна курица. Две утки."]
    ),
    Event(
        time_ms=4001,
        duration_ms=2000,
        chunks=["Два кричащих гуся."]
    )
]

EVENTS_UA = [
    Event(
        time_ms=60000,
        duration_ms=5000,
        chunks=[f"Путiн хуiло. {uuid.uuid4()}"]
    ),
    Event(
        time_ms=120000,
        duration_ms=5000,
        chunks=[f"Ole-ole! {uuid.uuid4()}"]
    ),
]


def test_get_all_pages():
    expected = [
        "553e3db2-3763-41a7-ae8a-bd4faa93131d",
        "8b4fcdb2-e90a-4a2b-951d-af46992d893a",
        "fe999aa7-a53a-448a-8b6f-3dcfe07ab434"
    ]

    pages = notion.get_pages(TEST_DATABASE_ID, page_size=2)
    assert set(expected) < set(pages)


def test_get_page_info():
    page = notion.get_page_info(TEST_PAGE_ID)
    assert page["url"] == "https://www.notion.so/Announcer-s-test-fe999aa7a53a448a8b6f3dcfe07ab434"  # noqa: E501


def test_parse_event():
    parse = notion._parse_event

    assert parse("00:00:00.000/00:00:00.000") == (0, 0)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0)


def test_get_events_from_test_data():
    with open("tests/data/transcript_block.json") as fd:
        block = json.load(fd)
        events = notion.get_events(block)

    assert events == EVENTS_EN


def test_get_transcripts_from_notion():
    en_EN, ru_RU, *_ = notion.get_all_transcripts(TEST_PAGE_ID)
    assert en_EN.lang == "en-US"
    assert en_EN.events == EVENTS_EN

    assert ru_RU.lang == "ru-RU"
    assert ru_RU.events == EVENTS_RU


def test_add_transcript():
    transcripts_before = notion.get_all_transcripts(TEST_PAGE_ID)
    transcript = notion.add_transcript(TEST_PAGE_ID, "uk-UK", EVENTS_UA)
    assert transcript.lang == "uk-UK"
    assert transcript.events == EVENTS_UA

    transcripts_after = notion.get_all_transcripts(TEST_PAGE_ID)
    assert transcripts_after == transcripts_before + [transcript]


def test_get_page_properties():
    with open("tests/data/page.json") as fd:
        page = json.load(fd)
    expected = {
        'Name': "Announcer's test",
        'Source Language': 'en-US',
        'Stage': 'Download',
        'Status': ['Transcribed'],
        'Target': ['ru-RU'],
        'Video': 'https://youtu.be/bhRaND9jiOA',
    }
    assert notion.get_page_properties(page) == expected
