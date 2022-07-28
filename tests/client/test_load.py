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


@pytest.mark.asyncio
async def test_load_ssmd(mock_client, monkeypatch):
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    with open("tests/lib/data/transcript/test.ssmd", "rb") as stream:
        task = await transcript.load(
            source=stream, method="SSMD", lang="en-US", session=session
        )
        result = await tasks.future(task)
        first, *_, last = result.events
        assert first == Event(
            time_ms=0,
            chunks=["Hello, Bill!", "How are you?"],
            duration_ms=1000,
            voice=Voice(character="Grace Hopper", pitch=0.0, speech_rate=1.0),
        )
        assert last == Event(
            time_ms=2000,
            chunks=["It was a huge mistake."],
            duration_ms=None,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.4),
        )


@pytest.mark.asyncio
async def test_load_subtitles(mock_client, monkeypatch):
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    task = await transcript.load(
        source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
        method="Subtitles",
        lang="en-US",
        session=session,
    )

    result = await tasks.future(task)
    first, *_, last = result.events

    assert first == Event(
        time_ms=0,
        chunks=["The way the work week works is the worst."],
        duration_ms=3011,
        voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
    )
    assert last == Event(
        time_ms=146570,
        chunks=["[soft brooding electronic music fades slowly]"],
        duration_ms=17996,
        voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
    )

    assert result.audio.startswith("https://")
    assert result.audio.endswith(".wav")

    assert result.video.startswith("https://")
    assert result.video.endswith(".mp4")


@pytest.mark.asyncio
async def test_load_transcribe(mock_client, monkeypatch):
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    task = await transcript.load(
        source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
        method="Machine B",
        lang="en-US",
        session=session,
    )

    result = await tasks.future(task)
    event, *_ = result.events

    assert event.time_ms == 140
    assert event.duration_ms == 145824

    chunk, *_ = event.chunks

    assert chunk.startswith("The way the work week works is the worst.")
    assert chunk.endswith(
        "If those sound intriguing, why not give it a try and see if weekend Wednesday works for you."  # noqa: E501
    )

    assert result.audio.startswith("https://")
    assert result.audio.endswith(".wav")

    assert result.video.startswith("https://")
    assert result.video.endswith(".mp4")
