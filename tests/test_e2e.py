from typing import Dict, List
from freespeech import language, speech, services, datastore
from freespeech.types import Transcript, Event
import requests


TEXT = [
    "One hen.\n\n",
    "Two ducks.\n\n",
    "Three squawking geese.\n\n",
    "Four limerick oysters.\n\n",
    "Five corpulent porpoises\n\n",
    "Six pairs of Don Alverzo's tweezers.\n\n",
    "Seven thousand Macedonians in full battle array.\n\n",
    "Eight brass monkeys from the ancient sacred crypts of Egypt.\n\n",
    "Nine apathetic, sympathetic, diabetic old men on roller skates, "
    "with a marked propensity towards procrastination and sloth."""
]


VOICEOVERS = [
    {
        'url': 'https://storage.googleapis.com/freespeech-tests/e2e/d7b18abc-e467-4f1c-ad5f-3b732bc2e3c3.mp4',
        'duration_ms': 1051846,
        'title': 'Volodymyr Zelensky addressed high-ranking officials and members of the UN Security Council.',
        'description': '"The Russian military and those who gave them orders must be brought to justice immediately for war crimes in Ukraine. Anyone who gave criminal orders and carried out them by killing our people will find himself under a tribunal that should be similar to the Nuremberg Trials. " Volodymyr Zelensky addressed high-ranking officials and members of the UN Security Council.',
        'tags': []
    },
    {
        'url': 'https://storage.googleapis.com/freespeech-tests/e2e/9b23a5f8-bc45-4dbf-824b-c02fa5b81a9f.mp4',
        'duration_ms': 1051846,
        'title': 'Владимир Зеленский обратился к чиновникам и членам Совбеза ООН.', 'description': '«Нужно немедленно привлекать российских военных и отдающих им приказы к ответственности за военные преступления на территории Украины. Каждый, кто отдавал преступные приказы и кто их выполнял, убивая наших людей, окажется под трибуналом, который должен быть аналогичен Нюрнбергскому процессу». Владимир Зеленский обратился к чиновникам и членам Совбеза ООН.',
        'tags': []
    },
    {
        'url': 'https://storage.googleapis.com/freespeech-tests/e2e/6af6227b-ce37-4e4a-8c8d-5f2315c76bb1.mp4',
        'duration_ms': 29332,
        'title': "Announcer's test",
        'description': "One hen\n\nTwo ducks\n\nThree squawking geese\n\nFour limerick oysters\n\nFive corpulent porpoises\n\nSix pairs of Don Alverzo's tweezers\n\nSeven thousand Macedonians in full battle array\n\nEight brass monkeys from the ancient sacred crypts of Egypt\n\nNine apathetic, sympathetic, diabetic old men on roller skates, with a marked propensity towards procrastination and sloth",
        'tags': ["announcer's", 'test']
    },
    {
        'url': 'https://storage.googleapis.com/freespeech-tests/e2e/fd84b896-342a-48a7-863e-df810a0f9a08.mp4',
        'duration_ms': 29332,
        'title': 'Тест диктора',
        'description': 'Одна курица\n\nДве утки\n\nТри кричащих гуся\n\nЧетыре лимерик устрицы\n\nПять тучных морских свиней\n\nШесть пар пинцетов Дона Альверзо\n\nСемь тысяч македонцев в полном боевом строю\n\nВосемь латунных обезьян из древних священных склепов Египта.\n\nДевять апатичных, сочувствующих стариков-диабетиков на роликовых коньках с заметной склонностью к прокрастинации и лени.',
        'tags': ["announcer's", 'test']
    }
]


def _remove_keys(target: Dict, keys: List[str]) -> Dict:
    return {
        key: value
        for key, value in target.items()
        if key not in keys
    }


def test_remove_keys():
    voiceover, *_ = VOICEOVERS
    assert _remove_keys(voiceover, []) == voiceover
    assert "url" in voiceover
    assert "url" not in _remove_keys(voiceover, ["url"])
    assert _remove_keys(voiceover, ["url"]) == _remove_keys(voiceover, ["url"])


def test_translate_synthesize():
    transcript = language.translate(
        text=Transcript(
            lang="en-US",
            events=[Event(
                time_ms=0,
                duration_ms=30_000,
                chunks=TEXT
            )]
        ),
        source=None,
        target="ru-RU"
    )

    audio = speech.synthesize(
        transcript=transcript,
        voice="ru-RU-WaveNet-A",
        storage_url="gs://freespeech-tests/e2e/"
    )

    assert abs(audio.duration_ms - 30_000) < 500


def test_download_transcribe_translate_synthesize_voiceover(
    monkeypatch, datastore_emulator
):
    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "gs://freespeech-tests/e2e/")

    url = "https://youtu.be/bhRaND9jiOA"
    transcript_id = services.download_and_transcribe(url, "en-US")
    translated_id = services.translate(transcript_id, lang="ru-RU")
    audio_id = services.synthesize(translated_id)
    voiceover_id = services.voiceover(url, audio_id)
    res = datastore.get(voiceover_id, "media")
    assert res is None


def test_voiceover_from_notion(
    monkeypatch, datastore_emulator
):
    PAGE_IDs = [
        "828608b4f74840f5bbf22994a05693a9",  # Z. UN Eng
        "de941561352b4b9d90e4d3c03936e6c9",  # Z. UN Rus
        "03182244413246de9d632b9e59548718",  # Announcer Test Eng
        "cb40a2e3cf3b4277b8d08e779c5ed306",  # Announcer Test Rus
    ]

    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "gs://freespeech-tests/e2e/")

    media = [
        services.create_voiceover_from_notion_page(page_id)
        for page_id in PAGE_IDs
    ]

    assert all(
        requests.head(m["url"]).status_code == 200
        for m in media
    )

    def remove_urls(items):
        return [_remove_keys(item, "url") for item in items]

    assert remove_urls(media) == remove_urls(VOICEOVERS)
