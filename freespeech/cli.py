import logging.config

import click
from aiohttp import web

from freespeech.api import chat, crud, dub, language, notion, pub, speech, telegram
from freespeech.lib import youtube

SERVICE_ROUTES = {
    "crud": crud.routes,
    "dub": dub.routes,
    "language": language.routes,
    "notion": notion.routes,
    "pub": pub.routes,
    "speech": speech.routes,
    "chat": chat.routes,
}

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
        "freespeech": {"level": logging.INFO, "handlers": ["console", "google"]},
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
@click.argument("services", nargs=-1)
def start(port: int, services):
    """Start HTTP API Server"""
    logger.info(f"Starting aiohttp server on port {port}")
    app = web.Application(logger=logger)

    for service in services:
        if service not in SERVICE_ROUTES:
            click.echo(
                f"Unknown service: {service}. "
                f"Expected values: {SERVICE_ROUTES.keys()}"
            )
            return -1
        routes = SERVICE_ROUTES[service]
        logger.info(f"Adding routes for {service}: {[r for r in routes]}")
        app.add_routes(routes)

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
    app = web.Application(logger=logger)

    routes = SERVICE_ROUTES["chat"]
    logger.info(f"Adding routes for chat: {[r for r in routes]}")
    app.add_routes(routes)

    telegram.start_bot(app)

    web.run_app(app, port=port)


if __name__ == "__main__":
    cli()
