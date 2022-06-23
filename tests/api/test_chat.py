from typing import Dict, Generator, Tuple

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


async def step(text: str, client) -> Tuple[str, str, Dict]:
    resp = await client.post("/say", json={"text": text})
    resp.raise_for_status()
    data = await resp.json()
    return data["text"], data["result"], data["state"]


@pytest.mark.asyncio
async def test_transcribe_translate_dub(const, client, aiohttp_server, monkeypatch):
    app = web.Application()
    app.add_routes(crud.routes)
    app.add_routes(dub.routes)
    _ = await aiohttp_server(app, port=8088)

    monkeypatch.setenv("FREESPEECH_CRUD_SERVICE_URL", "http://localhost:8088")
    monkeypatch.setenv("FREESPEECH_DUB_SERVICE_URL", "http://localhost:8088")

    VIDEO_URL = "https://www.youtube.com/watch?v=DEqXNfs_HhY"

    text = f"load {VIDEO_URL} in English using Machine B"
    reply, en_url, state = await step(text, client)
    assert state == {"language": ["en-US"], "method": ["Machine B"], "url": [VIDEO_URL]}
    assert en_url.startswith("https://docs.google.com/document/d")
    assert reply == f"Here you are: {en_url}"

    text = f"translate {en_url} to Russian"
    reply, ru_url, state = await step(text, client)
    assert state == {"language": ["ru-RU"], "url": [en_url]}
    assert ru_url.startswith("https://docs.google.com/document/d")
    assert reply == f"Here you are: {ru_url}"

    text = f"dub {ru_url}"
    reply, dub_url, state = await step(text, client)
    assert state == {"url": [ru_url]}
    assert dub_url.endswith(".mp4")
    assert reply == f"Here you are: {dub_url}"
