#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import logging.config
from dataclasses import replace

from telethon import Button, TelegramClient, events

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.lib import youtube
from freespeech.types import (
    Language,
    Operation,
    SpeechToTextBackend,
    assert_never,
    platform,
)

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
        "__main__": {"level": logging.INFO, "handlers": logging_handler},
    },
}
logging.config.dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)


api_id = env.get_telegram_api_id()
api_hash = env.get_telegram_api_hash()
client = TelegramClient("/tmp/freespeechbot", api_id, api_hash).start(
    bot_token=env.get_telegram_bot_token()
)

URL_SOLUTION_TEXT = (
    "Please send me a link to a YouTube video or Google Docs transcript."
)

user_state: dict[str, str] = {}


async def select_language(event, action: str, message: str):
    await event.reply(
        message,
        buttons=[
            Button.inline("EN", data=f"{action};en-US".encode("ASCII")),
            Button.inline("UA", data=f"{action};uk-UA".encode("ASCII")),
            Button.inline("ES", data=f"{action};es-ES".encode("ASCII")),
            Button.inline("FR", data=f"{action};fr-FR".encode("ASCII")),
            Button.inline("DE", data=f"{action};de-DE".encode("ASCII")),
            Button.inline("PT", data=f"{action};pt-PT".encode("ASCII")),
            Button.inline("RU", data=f"{action};ru-RU".encode("ASCII")),
        ],
    )


def log_user_action(event, action: str, **kwargs):
    sender = event.sender
    logger.info(
        f"User {event.sender_id} ({sender.username or (sender.first_name + ' ' + sender.last_name)}) {action} {kwargs}"  # noqa: E501
    )


async def estimate_operation_duration(url: str, operation: Operation) -> int:
    """Return estimated duration of an operation for a video or transcript in seconds.

    Args:
        url (str): URL of a video or transcript.
        operation (Operation): Operation to estimate duration for.

    Returns:
        Estimated duration in seconds.
    """
    _platform = platform(url)

    match _platform:
        case "YouTube":
            metric = youtube.get_meta(url).duration_ms
        case "Google" | "Notion":
            metric = len(
                " ".join(
                    " ".join(event.chunks)
                    for event in (await transcript.load(url)).events
                )
            )
        case "GCS":
            raise NotImplementedError("GCS is not supported yet")
        case _platform:
            assert_never(_platform)

    match operation:
        case "Transcribe":
            return round(metric / 2581)
        case "Translate":
            return round(metric / 102.679)
        case "Synthesize":
            return round(metric / 25)
        case _:
            assert_never(operation)


def seconds_to_human_readable(seconds: int) -> str:
    """Convert seconds to human readable format.

    Args:
        seconds (int): Seconds to convert.

    Returns:
        Human readable format.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    res = ""
    if hours:
        res += f" {hours} hour{'s' if hours > 1 else ''}"
    if minutes:
        res += f" {minutes} minute{'s' if minutes > 1 else ''}"
    if not res:
        res += f" {seconds} second{'s' if seconds > 1 else ''}"

    return res.strip()


async def handle_dub(url: str, is_smooth: bool, event):
    try:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(url, "Synthesize")
        )

        await event.reply(
            f"Alright! It should take me about {duration} to dub {url}",
            link_preview=False,
        )
        log_user_action(event, "dub", url=url, is_smooth=is_smooth)
        media_url = await synthesize.dub(
            await transcript.load(source=url), is_smooth=is_smooth
        )
        await event.reply(f"Here you are: {media_url}")
    except (ValueError, NotImplementedError, PermissionError) as e:
        await event.reply(str(e))
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")


async def handle_translate(url: str, lang: Language, event):
    try:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(url, "Translate")
        )

        await event.reply(
            f"Cool! It should take me about {duration} to translate {url} to {lang}.",
            link_preview=False,
        )
        log_user_action(event, "translate", url=url, lang=lang)
        transcript_url = await translate.translate(
            source=url, lang=lang, format="SSMD-NEXT", platform="Google"
        )
        await event.reply(
            f"Here you are: {transcript_url}. Now you can paste this link into this chat to dub.",  # noqa: E501
            link_preview=False,
        )
    except (ValueError, NotImplementedError, PermissionError) as e:
        await event.reply(str(e))
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")


async def handle_transcribe(
    url: str, lang: Language, backend: SpeechToTextBackend, event
):
    try:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(url, "Transcribe")
        )

        await event.reply(
            f"Sure! It should take me about {duration} to transcribe {url} in {lang} using {backend}.",  # noqa: E501
            link_preview=False,
        )
        log_user_action(event, "transcribe", url=url, lang=lang, backend=backend)
        t = await transcribe.transcribe(url, lang=lang, backend=backend)
        # NOTE: Bill seems to be the most popular. Doing this here because changing the
        # default in the library would break existing code.
        t = replace(
            t,
            events=[
                replace(event, voice=replace(event.voice, character="Bill"))
                for event in t.events
            ],
        )
        transcript_url = await transcript.save(
            transcript=t,
            platform="Google",
            format="SSMD-NEXT",
            location=None,
        )
        await event.reply(
            f"Here you are: {transcript_url}. Now you can paste this link into this chat to translate or dub.",  # noqa: E501
            link_preview=False,
        )
    except (ValueError, NotImplementedError, PermissionError) as e:
        await event.reply(str(e))
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")


@client.on(events.CallbackQuery())
async def handle_callback(event):
    action = event.data.decode("ASCII")
    url = user_state.get(event.sender_id, None)

    if url is None:
        raise ValueError("URL is missing")

    if action == "dub":
        await handle_dub(url, is_smooth=True, event=event)
    elif action == "translate":
        await select_language(event, action, "What language to translate to?")
    elif action in ("subtitles", "speech_recognition"):
        await select_language(event, action, "What's the original language?")
    elif action.startswith("translate;"):
        _, lang = action.split(";")
        await handle_translate(url, lang, event)
    elif action.startswith("subtitles;"):
        _, lang = action.split(";")
        await handle_transcribe(url, lang, "Subtitles", event)
    elif action.startswith("speech_recognition;"):
        _, lang = action.split(";")
        await handle_transcribe(url, lang, "Machine D", event)
    else:
        raise ValueError(f"Unknown action: {action}")


@client.on(events.NewMessage(pattern="/start"))
async def handle_start(event):
    await event.reply(
        f"Welcome to Freespeech! I am here to help you with video transcrition, translation and dubbing.\n{URL_SOLUTION_TEXT}"  # noqa: E501
    )


@client.on(events.NewMessage(pattern=r".*"))
async def url_handler(event):
    urls = [
        url for url in event.raw_text.split(" ") if url.strip().startswith("https://")
    ]

    if not urls:
        await event.reply(f"No links found in your message. {URL_SOLUTION_TEXT}")
        return

    url = urls[0]

    try:
        _platform = platform(url)
    except ValueError as e:
        await event.reply(str(e))
        logger.exception(e)
        return

    match _platform:
        case "YouTube":
            user_state[event.sender_id] = url
            await event.reply(
                "Create transcript using Subtitles or Speech Recognition?",
                buttons=[
                    Button.inline("Subtitles", data="subtitles".encode("ASCII")),
                    Button.inline(
                        "Speech Recognition", data="speech_recognition".encode("ASCII")
                    ),
                ],
            )
        case "Google" | "Notion":
            user_state[event.sender_id] = url
            await event.reply(
                "Translate or dub?",
                buttons=[
                    Button.inline("Translate", data="translate".encode("ASCII")),
                    Button.inline("Dub", data="dub".encode("ASCII")),
                ],
            )
        case "GCS":
            raise NotImplementedError("GCS is not supported yet")
        case x:
            assert_never(x)


if __name__ == "__main__":
    logger.info("Starting Telegram client")
    client.start()
    client.run_until_disconnected()
