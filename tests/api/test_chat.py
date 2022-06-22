from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.api import chat, crud, dub


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(chat.routes)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_transcribe(const, client, aiohttp_server, monkeypatch):
    app = web.Application()
    app.add_routes(crud.routes)
    app.add_routes(dub.routes)
    _ = await aiohttp_server(app, port=8088)

    monkeypatch.setenv("FREESPEECH_CRUD_SERVICE_URL", "http://localhost:8088")

    VIDEO_URL = const.ANNOUNCERS_TEST_VIDEO_URL
    # VIDEO_URL = "https://www.youtube.com/watch?v=U93QRMcQU5Y"
    LANGUAGE = const.ANNOUNCERS_TEST_VIDEO_LANGUAGE
    # LANGUAGE = "English"

    text = f"load {VIDEO_URL} in {LANGUAGE} using Subtitles"  # noqa: E501
    params = {"text": text}

    resp = await client.post("/say", json=params)
    data = await resp.json()

    assert data["url"].startswith("https://docs.google.com/document/d")
    assert data["text"] == f"Here you are: {data['url']}"

    text = f"transcribe {VIDEO_URL} from {LANGUAGE} using Machine B"  # noqa: E501
    params = {"text": text}

    resp = await client.post("/say", json=params)
    data = await resp.json()

    assert data["url"].startswith("https://docs.google.com/document/d")
    assert data["text"] == f"Here you are: {data['url']}"


@pytest.mark.asyncio
async def test_dub(client, aiohttp_server, monkeypatch):
    PAGE_URL = "https://docs.google.com/document/d/1FQEWOvJPq3_KR7pm2-L_GWqHgKRP9iq0Cx1vwNGCptg/edit#"

    app = web.Application()
    app.add_routes(crud.routes)
    app.add_routes(dub.routes)
    _ = await aiohttp_server(app, port=8088)

    monkeypatch.setenv("FREESPEECH_CRUD_SERVICE_URL", "http://localhost:8088")

    text = f"dub {PAGE_URL}"  # noqa: E501
    params = {"text": text}

    resp = await client.post("/say", json=params)
    data = await resp.json()

    assert data["url"].startswith("https://docs.google.com/document/d")
    assert data["text"] == f"Here you are: {data['url']}"
