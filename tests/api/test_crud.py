import logging
from typing import Generator
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.api import crud
from tests import commons

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(crud.routes)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_clip_upload_and_get(client):
    params = {
        "url": commons.ANNOUNCERS_TEST_VIDEO_URL,
        "lang": commons.ANNOUNCERS_TEST_VIDEO_LANGUAGE,
    }

    resp = await client.post("/clips/upload", json=params)
    clip = await resp.json()

    resp = await client.get(f"/clips/{clip['_id']}")
    assert clip == await resp.json()

    url = quote_plus(commons.ANNOUNCERS_TEST_VIDEO_URL)
    resp = await client.get(f"/clips/latest/{url}/en-US")
    latest = await resp.json()
    assert clip == latest


@pytest.mark.asyncio
async def test_clip_latest_and_update(client):
    url = quote_plus(commons.ANNOUNCERS_TEST_VIDEO_URL)
    resp = await client.get(f"/clips/latest/{url}")
    clips = await resp.json()

    resp = await client.get(f"/clips/latest/{url}/en-US")
    clip_en_us = await resp.json()

    assert clips["en-US"] == clip_en_us

    clip_ru_ru = {**clip_en_us, "lang": "ru-RU"}
    resp = await client.post(f"/clips/{clip_en_us['_id']}", json=clip_ru_ru)
    clip_ru_ru_new = await resp.json()

    resp = await client.get(f"/clips/latest/{url}/ru-RU")
    resp.raise_for_status()

    ignored = ("_id", "last_updated")
    clip_ru_ru = {k: v for k, v in clip_ru_ru.items() if k not in ignored}
    new = {k: v for k, v in clip_ru_ru_new.items() if k not in ignored}

    assert new["parent_id"] == clip_en_us["_id"]


@pytest.mark.asyncio
async def test_get_video(client):
    url = quote_plus(commons.ANNOUNCERS_TEST_VIDEO_URL)
    resp = await client.get(f"/clips/latest/{url}/en-US")
    clip_en_us = await resp.json()

    resp = await client.get(f"/clips/{clip_en_us['_id']}/video")
    video = await resp.json()

    video_gs, _ = clip_en_us["video"]
    assert video["url"] == video_gs.replace("gs://", "https://storage.googleapis.com/")
