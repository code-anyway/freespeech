import logging
import logging.config
from dataclasses import dataclass
from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

from freespeech.lib.tasks.tasks import dummy_schedule

LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "brief": {"format": "%(message)s"},
        "default": {
            "format": "%(asctime)s %(levelname)-8s %(name)-15s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "freespeech": {"level": logging.INFO, "handlers": ["console"]},
        "aiohttp": {"level": logging.INFO, "handlers": ["console"]},
        "root": {"level": logging.INFO, "handlers": ["console"]},
        "": {"level": logging.INFO, "handlers": ["console"]},
    },
}
logging.config.dictConfig(LOGGING_CONFIG)


@dataclass(frozen=True)
class Const:
    ANNOUNCERS_TEST_VIDEO_URL = "https://youtu.be/bhRaND9jiOA"
    ANNOUNCERS_TEST_VIDEO_LANGUAGE = "en-US"


@pytest.fixture
def const():
    return Const


@pytest_asyncio.fixture
async def client_session(
    aiohttp_client, monkeypatch
) -> Generator[AiohttpClient, None, None]:
    from freespeech.api import chat, edge, media, middleware, transcript

    app = web.Application(middlewares=[middleware.persist_results])
    app.add_routes(edge.routes(dummy_schedule))
    app.add_routes(media)
    app.add_routes(chat)
    app.add_routes(transcript)

    port = 8080
    client = await aiohttp_client(app, port=port)

    monkeypatch.setenv("FREESPEECH_TRANSCRIPT_SERVICE_URL", f"http://localhost:{port}")
    monkeypatch.setenv("FREESPEECH_MEDIA_SERVICE_URL", f"http://localhost:{port}")
    monkeypatch.setenv("FREESPEECH_CHAT_SERVICE_URL", f"http://localhost:{port}")

    return client


@pytest.fixture
def mock_client(client_session):
    def create(*args, **kwargs):
        return client_session

    return create
