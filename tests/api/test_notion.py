import json
import uuid


from freespeech.api import notion
from freespeech.types import Event


ANNOUNCERS_TEST_PROJECT_PAGE_ID = "fe999aa7a53a448a8b6f3dcfe07ab434"
TRANSCRIPT_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"
PROJECT_DATABASE_ID = "4d8d51229d854929b193a13604bf47dc"
ANNOUNCERS_TEST_VIDEO_URL = "https://youtu.be/bhRaND9jiOA"


SHORT_EVENT_1_EN = Event(time_ms=1001,
                         duration_ms=1000,
                         chunks=["One hen. Two ducks."])
SHORT_EVENT_2_EN = Event(time_ms=4001,
                         duration_ms=2000,
                         chunks=["Three squawking geese."])


SHORT_EVENT_1_RU = Event(time_ms=1001,
                         duration_ms=1000,
                         chunks=["Одна курица. Две утки."])
SHORT_EVENT_2_RU = Event(time_ms=4001,
                         duration_ms=2000,
                         chunks=["Два кричащих гуся."])


SHORT_EVENT_1_UA = Event(time_ms=60000,
                         duration_ms=5000,
                         chunks=[f"Путiн хуiло. {uuid.uuid4()}"])
SHORT_EVENT_2_UA = Event(time_ms=120000,
                         duration_ms=5000,
                         chunks=[f"Ole-ole! {uuid.uuid4()}"])


LONG_EVENT_EN = Event(time_ms=0,
                      duration_ms=29000,
                      chunks=['One hen. Two ducks. Three squawking geese. Four '    # noqa E501
                              'limerick oysters. Five corpulent porpoises. Six '    # noqa E501
                              "pairs of Don Alverzo's tweezers. Seven thousand "    # noqa E501
                              'Macedonians in full battle array. Eight brass '
                              'monkeys from the ancient sacred crypts of Egypt. '   # noqa E501
                              'Nine apathetic, sympathetic, diabetic old men on '   # noqa E501
                              'roller skates, with a marked propensity towards '    # noqa E501
                              'procrastination and sloth.'])

LONG_EVENT_RU = Event(time_ms=0,
                      duration_ms=29000,
                      chunks=['Одна курица. Две утки. Три кричащих гуся. Четыре '    # noqa E501
                              'лимерик устрицы. Пять тучных дельфинов. Шесть пар '   # noqa E501
                              'пинцетов Дона Альверзо. Семь тысяч македонцев в '     # noqa E501
                              'полном боевом строю. Восемь латунных обезьян из '     # noqa E501
                              'древних священных склепов Египта. Девять апатичных, ' # noqa E501
                              'сочувствующих стариков-диабетиков на роликовых '
                              'коньках с заметной склонностью к прокрастинации и '   # noqa E501
                              'лени.'])


def test_get_all_pages():
    pages = notion.get_pages(PROJECT_DATABASE_ID, page_size=2)
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
            f"https://api.notion.com/v1/blocks/{42}/children",
            json=block)
        events = notion.get_transcript(42)

    assert events == [SHORT_EVENT_1_EN, SHORT_EVENT_2_EN]


def test_get_transcripts_from_notion():
    transcripts = notion.get_transcripts(database_id=TRANSCRIPT_DATABASE_ID,
                                         url=ANNOUNCERS_TEST_VIDEO_URL)
    assert transcripts == {"en-US": [LONG_EVENT_EN], "ru-RU": [LONG_EVENT_RU]}


def test_add_transcript():
    page = notion.add_transcript(project_database_id=PROJECT_DATABASE_ID,
                                 transcript_database_id=TRANSCRIPT_DATABASE_ID,
                                 url=ANNOUNCERS_TEST_VIDEO_URL,
                                 lang="uk-UK",
                                 title="Who is Mr. Putin?",
                                 events=[LONG_EVENT_EN])
    assert notion.get_transcript(page) == [LONG_EVENT_EN]


def test_get_page_properties(requests_mock):
    with open("tests/api/data/notion/page.json") as fd:
        page = json.load(fd)
        requests_mock.get(
            f"https://api.notion.com/v1/pages/{42}",
            json=page)
    expected = {
        'Name': "Announcer's test",
        'Source Language': 'en-US',
        'Stage': 'Download',
        'Status': ['Transcribed'],
        'Target': ['ru-RU'],
        'Video': 'https://youtu.be/bhRaND9jiOA',
    }
    assert notion.get_page_properties(42) == expected
