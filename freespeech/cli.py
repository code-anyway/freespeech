import logging
import logging.config

import click
from aiohttp import web

from freespeech import api
from freespeech.lib import youtube

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
        "google": {"class": "freespeech.logging.GoogleCloudLoggingHandler"},
    },
    "loggers": {
        "freespeech": {
            "level": logging.INFO, "handlers": ["console", "google"]},
        "aiohttp": {"level": logging.INFO, "handlers": ["console", "google"]},
    },
}
logging.config.dictConfig(LOGGING_CONFIG)


logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli():
    "null"


@cli.command(name="start")
@click.option(
    "-p",
    "--port",
    required=False,
    default=8080,
    type=int,
    help="HTTP port to listen on",
)
def start(port: int):
    """Start HTTP API Server"""
    logger.info(f"Starting aiohttp server on port {port}")
    app = web.Application(logger=logger)
    app.add_routes(api.routes)
    web.run_app(app, port=port)


@cli.command(name="authorize")
@click.option(
    "-s",
    "--secret_file",
    required=True,
    help=(
        "Client secret file, i.e. generated from Google Cloud Console:"
        " https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps#python"  # noqa: E501
    ),
)
@click.option(
    "-o",
    "--output_file",
    required=True,
    help="Output file to store credentials JSON",
)
def authorize(secret_file, output_file):
    youtube.authorize(secret_file=secret_file, credentials_file=output_file)


@cli.command(name="upload")
@click.option("-v", "--video_file", required=True, help="Video file to upload")
@click.option(
    "-m",
    "--meta_file",
    required=True,
    help="JSON containing YouTube meta data",
)
@click.option(
    "-c",
    "--credentials_file",
    required=True,
    help="Credentials file obtained via `authorize` command.",
)
def upload(video_file, meta_file, credentials_file):
    youtube.upload(
        video_file=video_file,
        meta_file=meta_file,
        credentials_file=credentials_file,
    )
