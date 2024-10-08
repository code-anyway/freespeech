import logging
import logging.config
from dataclasses import dataclass

import pytest

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
