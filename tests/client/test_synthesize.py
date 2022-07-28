import asyncio
from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.client import tasks, transcript, client
from freespeech.types import Error, Event, Settings, Transcript, Voice

ANNOUNCERS_TEST_TRANSCRIPT_RU = Transcript(
    settings=Settings(),
    lang="ru-RU",
    events=[
        Event(
            time_ms=0,
            duration_ms=29000,
            voice=Voice(character="Alonzo Church"),
            chunks=[
                "Одна курица. Две утки. Три кричащих гуся. Четыре "
                "лимерик устрицы. Пять тучных дельфинов. Шесть пар "
                "пинцетов Дона Альверзо. Семь тысяч македонцев в "
                "полном боевом строю. Восемь латунных обезьян из "
                "древних священных склепов Египта. Девять апатичных, "
                "сочувствующих стариков-диабетиков на роликовых "
                "коньках с заметной склонностью к прокрастинации и "
                "лени."
            ],
        )
    ],
)


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
async def test_synthesize_basic(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    test_ru = Transcript(
        lang="ru-RU",
        events=[
            Event(
                time_ms=0,
                chunks=["Путин хуйло!"],
            )
        ],
    )

    result = await transcript.synthesize(test_ru, session=session)
    if isinstance(result, Error):
        assert False, result.message

    assert result.message == "Estimated wait time: 5 minutes"

    task_result = await tasks.future(result)
    if isinstance(task_result, Error):
        assert False, task_result.message

    assert task_result.audio
    assert task_result.audio.endswith(".wav")
    assert task_result.audio.startswith("https://")

    await asyncio.sleep(1.0)
