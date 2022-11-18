import logging
import logging.config

import click

from freespeech import env
from freespeech.lib import youtube

logging_handler = ["google" if env.is_in_cloud_run() else "console"]

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
        "google": {"class": "google.cloud.logging.handlers.StructuredLogHandler"},
    },
    "loggers": {
        "freespeech": {"level": logging.INFO, "handlers": logging_handler},
        "aiohttp": {"level": logging.INFO, "handlers": logging_handler},
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
@click.argument("services", nargs=-1)
def start(port: int, services):
    # Start FastAPI server
    return


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


if __name__ == "__main__":
    cli()
