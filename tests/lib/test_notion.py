from datetime import datetime, timezone
import json
import uuid

from freespeech.lib import notion
from freespeech.types import Event, Meta, Voice

ANNOUNCERS_TEST_PROJECT_PAGE_ID = "fe999aa7a53a448a8b6f3dcfe07ab434"
ANNOUNCERS_TEST_TRANSCRIPT_PAGE_ID_EN = "03182244413246de9d632b9e59548718"
ANNOUNCERS_TEST_VIDEO_URL = "https://youtu.be/bhRaND9jiOA"
PROJECT_DATABASE_ID = "4d8d51229d854929b193a13604bf47dc"
TRANSCRIPT_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"


SHORT_EVENT_1_EN = Event(time_ms=1001, duration_ms=1000, chunks=["One hen. Two ducks."])
SHORT_EVENT_2_EN = Event(
    time_ms=4001, duration_ms=2000, chunks=["Three squawking geese."]
)


SHORT_EVENT_1_RU = Event(
    time_ms=1001, duration_ms=1000, chunks=["Одна курица. Две утки."]
)
SHORT_EVENT_2_RU = Event(time_ms=4001, duration_ms=2000, chunks=["Два кричащих гуся."])


SHORT_EVENT_1_UK = Event(
    time_ms=60000, duration_ms=5000, chunks=[f"Путiн хуiло. {uuid.uuid4()}"]
)
SHORT_EVENT_2_UK = Event(
    time_ms=120000, duration_ms=5000, chunks=[f"Ole-ole! {uuid.uuid4()}"]
)


LONG_EVENT_EN = Event(
    time_ms=0,
    duration_ms=29000,
    chunks=[
        "One hen. Two ducks. Three squawking geese. Four "
        "limerick oysters. Five corpulent porpoises. Six "
        "pairs of Don Alverzo's tweezers. Seven thousand "
        "Macedonians in full battle array. Eight brass "
        "monkeys from the ancient sacred crypts of Egypt. "
        "Nine apathetic, sympathetic, diabetic old men on "
        "roller skates, with a marked propensity towards "
        "procrastination and sloth."
    ],
)

LONG_EVENT_RU = Event(
    time_ms=0,
    duration_ms=29000,
    chunks=[
        "Одна курица. Две утки. Три кричащих гуся. Четыре "
        "лимерик устрицы. Пять тучных дельфинов. Шесть пар "
        "пинцетов Дона Альверзо. Семь тысяч македонцев в "
        "полном боевом строю. Восемь латунных обезьян из "
        "древних священных склепов Египта. Девять апатичных, "
        "сочувствующих стариков-диабетиков на роликовых "
        "коньках с заметной склонностью к прокрастинации и "
        "лени."
    ],
)


def test_parse_event():
    parse = notion.parse_time_interval

    assert parse("00:00:00.000/00:00:00.000") == (0, 0)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0)


def test_create_update_get_transcript():
    # PAGE_ID = "cfe33f84267f43ec8f5c7e46b2daf0be"
    TEST_TRANSCRIPT = notion.Transcript(
        title="Test Transcript",
        origin="https://",
        lang="en-US",
        source="Subtitles",
        events=[SHORT_EVENT_1_EN, SHORT_EVENT_2_EN],
        voice=Voice(character="Alan Turing", pitch=1.0),
        weights=(2, 10),
        meta=Meta(title="Foo", description="Bar", tags=["one", "two"]),
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        dub_url="https://dub",
        clip_id="uuid",
        _id=None
    )
    transcript = notion.put_transcript(TRANSCRIPT_DATABASE_ID, TEST_TRANSCRIPT)
    _id = transcript._id
    assert notion.get_transcript(_id) == transcript

    TEST_TRANSCRIPT_UPDATED = notion.Transcript(
        title="Test Transcript Updated",
        origin="https://Updated",
        lang="ru-RU",
        source="Translate",
        events=[SHORT_EVENT_1_RU, SHORT_EVENT_2_RU],
        voice=Voice(character="Grace Hopper", pitch=2.0),
        weights=(3, 30),
        meta=Meta(title="Updated Foo", description="Updated Bar", tags=["three", "four"]),
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        dub_url="https://dub/updated",
        clip_id="uuid-updated",
        _id=_id
    )
    transcript = notion.put_transcript(TRANSCRIPT_DATABASE_ID, TEST_TRANSCRIPT_UPDATED)
    assert transcript._id == _id
    assert notion.get_transcript(_id) == TEST_TRANSCRIPT_UPDATED


def test_add_transcript():
    page = notion.add_transcript(
        database_id=TRANSCRIPT_DATABASE_ID,
        video_url=ANNOUNCERS_TEST_VIDEO_URL,
        lang="uk-UK",
        title="Who is Mr. Putin?",
        events=[SHORT_EVENT_1_UK, SHORT_EVENT_2_UK],
    )
    t_uk = notion.get_transcript(page_id=page)
    assert t_uk == [SHORT_EVENT_1_UK, SHORT_EVENT_2_UK]


def test_get_properties(requests_mock):
    with open("tests/lib/data/notion/page.json") as fd:
        page = json.load(fd)
        requests_mock.get(f"https://api.notion.com/v1/pages/{42}", json=page)
    expected = {
        "Name": "Announcer's test",
        "Source Language": "en-US",
        "Stage": "Download",
        "Status": ["Transcribed"],
        "Target": ["ru-RU"],
        "Video": "https://youtu.be/bhRaND9jiOA",
    }
    assert notion.get_properties(42) == expected
