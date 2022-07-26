from typing import Generator

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

import freespeech.client.media as media_client
from freespeech.api import media


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(media.routes)
    return await aiohttp_client(app, timeout=aiohttp.ClientTimeout(total=10000))


@pytest.mark.skip(reason="Long test, enable to call ingest")
@pytest.mark.asyncio
async def test_jsononly_ingest(client):
    import time

    start_time = time.time()

    # resp = await media_client.ingest(
    #     "https://www.youtube.com/watch?v=Gm4qV0wX8f0", session=client
    # )
    print("--- %s seconds ---" % (time.time() - start_time))
