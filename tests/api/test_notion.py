import json
import uuid


from freespeech.api import notion
from freespeech.types import Event


TEST_PAGE_ID = "fe999aa7a53a448a8b6f3dcfe07ab434"
TEST_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"
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
    pages = notion.get_pages(TEST_DATABASE_ID, page_size=2)
    assert pages


def test_parse_event():
    parse = notion._parse_event

    assert parse("00:00:00.000/00:00:00.000") == (0, 0)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0)


def test_get_transcript_from_test_data(requests_mock):
    with open("tests/api/data/notion/transcript_block.json") as fd:
        block = json.load(fd)
        requests_mock.get(
            f"https://api.notion.com/v1/blocks/{TEST_PAGE_ID}/children",
            json=block)
        events = notion.get_transcript(TEST_PAGE_ID)

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


def test_get_page_properties(requests_mock):
    with open("tests/api/data/notion/page.json") as fd:
        page = json.load(fd)
        requests_mock.get(
            f"https://api.notion.com/v1/pages/{TEST_PAGE_ID}",
            json=page)
    expected = {
        'Name': "Announcer's test",
        'Source Language': 'en-US',
        'Stage': 'Download',
        'Status': ['Transcribed'],
        'Target': ['ru-RU'],
        'Video': 'https://youtu.be/bhRaND9jiOA',
    }
    assert notion.get_page_properties(TEST_PAGE_ID) == expected
