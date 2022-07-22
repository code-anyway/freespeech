from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.api import synthesize
from freespeech.client import transcript
from freespeech.types import Settings, Transcript, Event, Voice, Error


ANNOUNCERS_TEST_TRANSCRIPT_RU = Transcript(
    title=None,
    source=None,
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
    video=None,
    audio=None,
)


@pytest_asyncio.fixture
async def client(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    app = web.Application()
    # fill route table
    app.add_routes(synthesize.routes)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_synthesize_basic(client):
    hello_ru = Transcript(
        lang="ru-RU",
        events=[
            Event(
                time_ms=0,
                chunks=["Привет!"],
                duration_ms=None,
            )
        ],
        settings=Settings(),
        title=None,
        source=None,
        video=None,
        audio=None,
    )

    result = await transcript.synthesize(hello_ru, session=client)

    if isinstance(result, Error):
        assert False, result.message

    new_transcript = await result

    assert new_transcript.audio == ""
