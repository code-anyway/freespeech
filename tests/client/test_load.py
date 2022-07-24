from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.client import client, tasks, transcript
from freespeech.types import Event, Voice


@pytest_asyncio.fixture
async def client_session(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    from freespeech.api import media, transcript

    app = web.Application()

    app.add_routes(transcript.routes)
    app.add_routes(media.routes)

    return await aiohttp_client(app)


@pytest.fixture
def mock_client(client_session):
    def create(*args, **kwargs):
        return client_session

    return create


@pytest.mark.asyncio
async def test_load_srt(mock_client, monkeypatch):
    monkeypatch.setattr(client, "create", mock_client)

    session = mock_client()

    with open("tests/lib/data/transcript/fmj.srt", "rb") as stream:
        task = await transcript.load(
            source=stream, method="SRT", lang="en-US", session=session
        )
        result = await tasks.future(task)
        first, *_, last = result.events
        assert first == Event(
            time_ms=27110,
            chunks=['"America has heard the bugle call'],
            duration_ms=5050,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
        )
        assert last == Event(
            time_ms=6716480,
            chunks=["And I am not afraid."],
            duration_ms=1580,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
        )
