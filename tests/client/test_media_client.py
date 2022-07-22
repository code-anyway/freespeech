from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

import freespeech.client.media as media_client
from freespeech.api import crud


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(crud.routes)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_jsononly_ingest(client):
    resp = await media_client.ingest("abc", output_types=[], session=client)
    assert resp


@pytest.mark.asyncio
async def test_stream_ingest(client):
    pass
    # resp = await media_client.ingest("abc", output_types=[], session=client)
