import pytest
from aiohttp import web

from freespeech.api import crud, dub

ANNOUNCERS_TEST_VIDEO_URL = "https://youtu.be/bhRaND9jiOA"

ANNOUNCERS_TEST_TRANSCRIPT_RU = [
    {
        "time_ms": 0,
        "duration_ms": 29000,
        "chunks": [
            "Одна курица. Две утки. Три кричащих гуся. Четыре "
            "лимерик устрицы. Пять тучных дельфинов. Шесть пар "
            "пинцетов Дона Альверзо. Семь тысяч македонцев в "
            "полном боевом строю. Восемь латунных обезьян из "
            "древних священных склепов Египта. Девять апатичных, "
            "сочувствующих стариков-диабетиков на роликовых "
            "коньках с заметной склонностью к прокрастинации и "
            "лени."
        ],
    }
]


@pytest.mark.asyncio
async def test_create_dub(aiohttp_client):
    app = web.Application()
    # fill route table
    app.add_routes(dub.routes)
    app.add_routes(crud.routes)

    client = await aiohttp_client(app)

    params = {
        "transcript": ANNOUNCERS_TEST_TRANSCRIPT_RU,
        "characters": {"default": "Alan Turing"},
        "lang": "ru-RU",
        "pitch": 0.0,
        "weights": [2, 10],
    }

    _id = "6ea2eef0-7fbe-4ebc-bf08-d413e0006d4d"  # Announcer's test
    resp = await client.post(f"/clips/{_id}/dub", json=params)
    clip_ru_ru = await resp.json()

    assert clip_ru_ru["_id"] != _id
    assert clip_ru_ru["video"]

    video_url, _ = clip_ru_ru["video"]
    assert video_url

    voices = [item["voice"] for item in clip_ru_ru["transcript"]]
    assert all(voice["pitch"] == 0.0 for voice in voices)
    assert all(voice["character"] == "Alan Turing" for voice in voices)
