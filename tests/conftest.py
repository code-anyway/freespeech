import logging
import logging.config
from dataclasses import dataclass
from typing import Generator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient

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


def add_service_prefix(prefix: str, routes):
    for route in routes:
        yield web.route(
            method=route.method, path=prefix + route.path, handler=route.handler
        )


@pytest_asyncio.fixture
async def client_session(aiohttp_client) -> Generator[AiohttpClient, None, None]:
    from freespeech.api import chat, media, transcript

    app = web.Application()

    app.add_routes(add_service_prefix("/transcript", transcript.routes))
    app.add_routes(add_service_prefix("/media", media.routes))
    app.add_routes(add_service_prefix("/chat", chat.routes))

    return await aiohttp_client(app)


@pytest.fixture
def mock_client(client_session):
    def create(*args, **kwargs):
        return client_session

    return create
