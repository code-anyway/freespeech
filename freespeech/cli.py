import logging.config

import aiohttp.web
import click
from aiohttp import ClientResponseError, web

from freespeech import env
from freespeech.api import chat, media, telegram, transcript
from freespeech.lib import youtube

SERVICE_ROUTES = {
    "media": media.routes,
    "transcript": transcript.routes,
    "chat": chat.routes,
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


@web.middleware
async def error_handler_middleware(request, handler):
    """Here we handle specific types of errors we know should be 'recoverable' or
    'user input errors', log them, and convert to HTTP Semantics"""
    try:
        resp = await handler(request)
        return resp
    except (AttributeError, NameError, ValueError, PermissionError, RuntimeError) as e:
        logger.warning(f"User input error: {e}")
        raise web.HTTPBadRequest(text=str(e)) from e
    except ClientResponseError as e:
        logger.warning(f"Downstream api call error: {e}")
        raise web.HTTPBadRequest(text=e.message) from e
    except aiohttp.web.HTTPError as e:
        logger.warning(f"HTTPError: {e}")
        raise e


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
    app = web.Application(logger=logger, middlewares=[error_handler_middleware])

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
    telegram.start_bot(port)


if __name__ == "__main__":
    cli()
