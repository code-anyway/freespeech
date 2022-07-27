from typing import Generator

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.client import client, media, tasks
from freespeech.types import Error


@pytest_asyncio.fixture
async def client_session(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    from freespeech.api import media

    app = web.Application()

    app.add_routes(media.routes)

    return await aiohttp_client(app, timeout=aiohttp.ClientTimeout(total=10000))


@pytest.fixture
def mock_client(client_session):
    def create(*args, **kwargs):
        return client_session

    return create


@pytest.mark.skip(reason="Long test, enable to call ingest")
@pytest.mark.asyncio
async def test_jsononly_ingest(client):
    import time

    start_time = time.time()

    # resp = await media_client.ingest(
    #     "https://www.youtube.com/watch?v=Gm4qV0wX8f0", session=client
    # )
    print("--- %s seconds ---" % (time.time() - start_time))


@pytest.mark.asyncio
async def test_ingest_youtube_short(mock_client, monkeypatch):
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    response = await media.ingest(
        "https://www.youtube.com/watch?v=hgV8mB-M9po", session=session
    )
    result = await tasks.future(response)
    if isinstance(result, Error):
        assert False, result.message

    assert result.audio.startswith("https://")
    assert result.audio.endswith(".wav")

    assert result.video.startswith("https://")
    assert result.video.endswith(".mp4")
