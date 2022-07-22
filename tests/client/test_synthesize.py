from typing import Any, Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.api import synthesize
from freespeech.client import tasks, transcript
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
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(synthesize.routes)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_synthesize_basic(client: Any) -> None:
    test_ru = Transcript(
        lang="ru-RU",
        events=[
            Event(
                time_ms=0,
                chunks=["Путин хуйло!"],
            )
        ],
    )

    result = await transcript.synthesize(test_ru, session=client)
    if isinstance(result, Error):
        assert False, result.message

    assert result.message == "Estimated wait time: 5 minutes"

    task_result = await tasks.future(result)
    if isinstance(task_result, Error):
        assert False, task_result.message

    assert task_result.audio
    assert task_result.audio.url.endswith(".wav")
    assert task_result.audio.url.startswith("https://")
