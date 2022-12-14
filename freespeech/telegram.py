#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import logging.config
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Literal

from telethon import Button, TelegramClient, events, hints
from telethon.utils import get_display_name

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.lib import youtube
from freespeech.types import (
    Language,
    Operation,
    SpeechToTextBackend,
    assert_never,
    is_language,
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


@dataclass(frozen=True)
class ConversationState:
    """State of a user conversation."""

    handler: Callable
    entity: hints.EntityLike

    user_message_id: int | None = None
    from_lang: Language | None = None
    to_lang: Language | None = None
    method: SpeechToTextBackend | None = None
    url: str | None = None


def to_language(lang: str) -> Language | None:
    """Converts human readable language name to BCP 47 tag."""
    lang.strip().lower()
    if lang in ("russian", "русский", "ru-RU"):
        return "ru-RU"
    elif lang in ("ukrainian", "українська", "украинский" "uk-UA"):
        return "uk-UA"
    elif lang in ("english", "английский", "en-US"):
        return "en-US"
    elif lang in ("spanish", "испанский", "español", "es-ES"):
        return "es-ES"
    elif lang in ("french", "французский", "français", "fr-FR"):
        return "fr-FR"
    elif lang in ("german", "немецкий", "deutsch", "de-DE"):
        return "de-DE"
    elif lang in ("portuguese", "португальский", "português", "pt-PT"):
        return "pt-PT"
    else:
        return None


def transcript_operation(
    state: ConversationState, message: str
) -> tuple[ConversationState, str | None, list[str] | None]:
    if message == "Translate":
        if state.to_lang is None:
            return (
                state,
                "Please select a language.",
                ["EN", "UA", "ES", "FR", "DE", "PT"],
            )
    if message == "Dub":
        return None, None, None

    if (lang := to_language(message)) is not None:
        state = replace(state, to_lang=lang)

    if state.url and state.to_lang:
        pass

    return state, None, None


user_state: dict[str, ConversationState] = {}


def log_user_action(action: str, **kwargs):
    logger.info(f"{action} {kwargs}")  # noqa: E501


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


async def _dub(url: str):
    try:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(url, "Synthesize")
        )

        await event.reply(
            f"Alright! It should take me about {duration} to dub {url}",
            link_preview=False,
        )
        log_user_action(
            "dub",
            url=url,
        )
        media_url = await synthesize.dub(
            await transcript.load(source=url), is_smooth=is_smooth
        )
        await event.reply(f"Here you are: {media_url}")
    except (ValueError, NotImplementedError, PermissionError) as e:
        await event.reply(str(e))
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")


async def _translate(url: str, lang: Language, event):
    try:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(url, "Translate")
        )

        await event.reply(
            f"Cool! It should take me about {duration} to translate {url} to {lang}.",
            link_preview=False,
        )
        log_user_action("translate", url=url, lang=lang)
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


async def _transcribe(url: str, lang: Language, backend: SpeechToTextBackend) -> str:
    try:
        log_user_action("transcribe", url=url, lang=lang, backend=backend)
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
        return f"Here you are: {transcript_url}. Now you can paste this link into this chat to translate or dub."  # noqa: E501

    except (ValueError, NotImplementedError, PermissionError) as e:
        return str(e)
    except Exception as e:
        logger.exception(e)
        return "Something went wrong. Please try again later."


def start(
    state: ConversationState,
    message: str,
) -> tuple[ConversationState, str | None, list[str] | None]:
    urls = [url for url in message.split(" ") if url.strip().startswith("https://")]

    if not urls:
        return state, f"No links found in your message. {URL_SOLUTION_TEXT}", None

    url = urls[0]

    try:
        _platform = platform(url)
    except ValueError as e:
        logger.exception(e)
        return state, str(e), []

    state = replace(state, url=url)
    match _platform:
        case "YouTube" | "GCS":
            return (
                replace(state, operation=media_operation),
                "Create transcript using Subtitles or Speech Recognition?",
                ["Subtitles", "Speech Recognition"],
            )
        case "Google" | "Notion":
            return (
                replace(state, operation=transcript_operation),
                "Would you like to translate, dub, or download the transcript as SRT or TXT?",
                ["Translate", "Dub", "SRT", "TXT"],
            )
        case x:
            assert_never(x)


async def media_operation(
    state: ConversationState, message: str
) -> tuple[ConversationState, str | None, list[str] | None]:
    if message in ("Subtitles", "Speech Recognition"):
        state = replace(state, method=message)

    if (lang := to_language(message)) is not None:
        state = replace(state, from_lang=lang)

    if state.method is None:
        return state, "Please select a method.", ["Subtitles", "Speech Recognition"]

    if state.from_lang is None:
        return state, "Please select a language.", ["EN", "UA", "ES", "FR", "DE", "PT"]

    if state.url and state.from_lang and state.method:
        duration = seconds_to_human_readable(
            await estimate_operation_duration(state.url, "Transcribe")
        )

        async def execute_and_notify(
            coro: Awaitable, entity: hints.EntityLike, reply_message_id: int | None
        ):
            message = await coro
            if reply_message_id is not None:
                await client.send_message(
                    entity, reply_to=reply_message_id, message=message
                )

        asyncio.create_task(
            execute_and_notify(
                _transcribe(state.url, state.from_lang, state.method),
                state.entity,
                state.user_message_id,
            )
        )

        return (
            ConversationState(handler=start, entity=state.entity),
            f"Sure! It should take me about {duration} to transcribe {state.url} in {state.from_lang} using {state.method}.",  # noqa: E501
            None,
        )

    return state, None, None


@client.on(events.NewMessage(pattern=r".*"))
async def event_handler(event):
    if event.raw_text == "/start":
        await event.reply(
            f"Welcome to Freespeech! I am here to help you with video transcription, translation and dubbing.\n{URL_SOLUTION_TEXT}"  # noqa: E501
        )
        return

    if event.sender_id not in user_state:
        user_state[event.sender_id] = ConversationState(handler=start, entity=event)
    user_state[event.sender_id], reply, buttons = user_state[event.sender_id].handler(
        user_state[event.sender_id], event.raw_text
    )  # noqa: E501
    await event.reply(
        reply,
        buttons=[
            Button.inline(button, data=button.encode("ASCII")) for button in buttons
        ],
    )  # noqa: E501


if __name__ == "__main__":
    logger.info("Starting Telegram client")
    client.start()
    client.run_until_disconnected()
