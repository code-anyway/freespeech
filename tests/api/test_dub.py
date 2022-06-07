from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient
from google.cloud import firestore  # type: ignore

from freespeech import env
from freespeech.api import crud, dub
from tests import commons

ANNOUNCERS_TEST_TRANSCRIPT_RU = [
    {
        "time_ms": 0,
        "duration_ms": 29000,
        "voice": {"character": "Alonzo Church"},
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


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(dub.routes)
    app.add_routes(crud.routes)
    return await aiohttp_client(app)


@pytest_asyncio.fixture
async def ensure_clip_id(client) -> str:
    firestore_client = firestore.AsyncClient(project=env.get_project_id())
    docs = (
        firestore_client.collection("clips")
        .where("origin", "==", commons.ANNOUNCERS_TEST_VIDEO_URL)
        .where("lang", "==", commons.ANNOUNCERS_TEST_VIDEO_LANGUAGE)
        .select("_id")
        .limit(1)
        .stream()
    )
    async for doc in docs:
        return doc.id

    # upload clip with CRUD api and return its id
    params = {"url": commons.ANNOUNCERS_TEST_VIDEO_URL, "lang": "en-US"}
    resp = await client.post("/clips/upload", json=params)
    clip = await resp.json()
    return clip["_id"]


@pytest.mark.asyncio
async def test_create_dub(client, ensure_clip_id):
    params = {
        "transcript": ANNOUNCERS_TEST_TRANSCRIPT_RU,
        "characters": {"default": "Alan Turing"},
        "lang": "ru-RU",
        "pitch": 0.0,
        "weights": [2, 10],
    }

    _id = ensure_clip_id  # Announcer's test
    resp = await client.post(f"/clips/{_id}/dub", json=params)
    clip_ru_ru = await resp.json()

    assert clip_ru_ru["_id"] != _id
    assert clip_ru_ru["video"]

    video_url, _ = clip_ru_ru["video"]
    assert video_url

    voices = [item["voice"] for item in clip_ru_ru["transcript"]]
    assert all(voice["pitch"] == 0.0 for voice in voices)
    assert all(voice["character"] == "Alonzo Church" for voice in voices)
