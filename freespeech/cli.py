import logging.config

import click
from aiohttp import web

from freespeech import env
from freespeech.api import chat, edge, media, middleware, transcript
from freespeech.api.middleware import error_handler_middleware
from freespeech.lib import youtube
from freespeech.lib.tasks import cloud_tasks

SERVICE_ROUTES = {
    "media": lambda: media.routes,
    "transcript": lambda: transcript.routes,
    "chat": lambda: chat.routes,
    "edge": lambda: edge.routes(
        schedule_fn=cloud_tasks.schedule, get_fn=cloud_tasks.get
    ),
}


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
    """Start HTTP API Server"""
    logger.info(f"Starting aiohttp server on port {port}")
    app = web.Application(
        logger=logger,
        middlewares=[error_handler_middleware, middleware.persist_results],
    )

    for service in services:
        if service not in SERVICE_ROUTES:
            click.echo(
                f"Unknown service: {service}. "
                f"Expected values: {SERVICE_ROUTES.keys()}"
            )
            return -1
        get_routes = SERVICE_ROUTES[service]
        app.add_routes(get_routes())

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


@click.option(
    "-p",
    "--port",
    required=False,
    default=8080,
    type=int,
    help="HTTP port to listen on",
)
@cli.command(name="start-telegram")
def start_telegram(port: int):
    from freespeech.api import telegram

    telegram.start_bot(port)


if __name__ == "__main__":
    cli()
