#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import logging.config
import tempfile
from dataclasses import dataclass, replace
from typing import Awaitable, Callable

from telethon import Button, TelegramClient, events
from telethon.tl.custom.message import Message

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.lib import youtube
from freespeech.lib.transcript import events_to_srt
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


@dataclass(frozen=True)
class Context:
    state: Callable
    message: Message | None = None
    from_lang: Language | None = None
    to_lang: Language | None = None
    method: SpeechToTextBackend | None = None
    url: str | None = None


@dataclass(frozen=True)
class Reply:
    message: str
    file: str | None = None
    buttons: list[str] | None = None


context: dict[int, Context] = {}


def log_user_action(action: str, **kwargs):
    logger.info(f"{action} {kwargs}")  # noqa: E501


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


async def _dub(url: str):
    media_url = await synthesize.dub(await transcript.load(source=url), is_smooth=True)
    return f"Here you are: {media_url}"


async def _translate(url: str, lang: Language):
    transcript_url = await translate.translate(
        source=url, lang=lang, format="SSMD-NEXT", platform="Google"
    )
    return f"Here you are: {transcript_url}. Paste this link into this chat to dub."


async def _transcribe(url: str, lang: Language, backend: SpeechToTextBackend) -> str:
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


async def estimate_operation_duration(url: str, operation: Operation) -> int | None:
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
        case x:
            assert_never(x)


def seconds_to_human_readable(seconds: int | None) -> str:
    """Convert seconds to human readable format.

    Args:
        seconds (int): Seconds to convert.

    Returns:
        Human readable format.
    """
    if seconds is None:
        return ""
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


async def send_message(ctx: Context, reply: Reply) -> None:
    assert ctx.message is not None

    _buttons = [
        Button.inline(button, data=button.encode("ASCII"))
        for button in reply.buttons or []
    ]
    file = reply.file if reply.file is not None else []
    await ctx.message.reply(
        message=reply.message,
        buttons=_buttons,
        file=file,
    )


async def schedule(ctx: Context, task: Awaitable, operation: Operation) -> str:
    assert ctx.url is not None

    async def execute_and_notify():
        try:
            log_user_action(action=operation, ctx=ctx)
            message = await task
        except (ValueError, NotImplementedError, PermissionError) as e:
            message = str(e)
        except Exception as e:
            logger.exception(e)
            message = "Something went wrong. Please try again later."

        await send_message(ctx, Reply(message))

    asyncio.create_task(execute_and_notify())

    return seconds_to_human_readable(
        await estimate_operation_duration(ctx.url, operation)
    )


def start(ctx: Context, message: Message) -> tuple[Context, Reply | None]:
    text = message.raw_text or ""
    urls = [url for url in text.split(" ") if url.strip().startswith("https://")]

    if not urls:
        return ctx, Reply(f"No links found in your message. {URL_SOLUTION_TEXT}")

    url = urls[0]

    try:
        _platform = platform(url)
    except ValueError as e:
        logger.exception(e)
        return ctx, Reply(str(e))

    ctx = replace(ctx, url=url, message=message)
    match _platform:
        case "YouTube" | "GCS":
            return replace(ctx, operation=media_operation), Reply(
                "Create transcript using Subtitles or Speech Recognition?",
                buttons=["Subtitles", "Speech Recognition"],
            )
        case "Google" | "Notion":
            return replace(ctx, operation=transcript_operation), Reply(
                "Would you like to translate, dub, or download the transcript as SRT or TXT?",  # noqa: E501
                buttons=["Translate", "Dub", "SRT", "TXT"],
            )
        case x:
            assert_never(x)


async def media_operation(
    ctx: Context, message: Message
) -> tuple[Context, Reply | None]:
    text = message.raw_text or ""

    if text in ("Subtitles", "Speech Recognition"):
        ctx = replace(ctx, method=text)

    if (lang := to_language(text)) is not None:
        ctx = replace(ctx, from_lang=lang)

    if ctx.method is None:
        return ctx, Reply(
            "Please select a method.", buttons=["Subtitles", "Speech Recognition"]
        )

    if ctx.from_lang is None:
        return ctx, Reply(
            "Please select or send the language.",
            buttons=["EN", "UA", "ES", "FR", "DE", "PT"],
        )

    if ctx.url and ctx.from_lang and ctx.method:
        duration = schedule(
            ctx, _transcribe(ctx.url, ctx.from_lang, ctx.method), "Transcribe"
        )
        return Context(state=start), Reply(
            f"Sure! Give me {duration} to transcribe {ctx.url} in {ctx.from_lang} using {ctx.method}.",  # noqa: E501
        )

    return ctx, None


async def transcript_operation(
    ctx: Context, message: Message
) -> tuple[Context, Reply | None]:
    text = message.raw_text or ""
    text = text.strip().lower()

    if text == "translate":
        if ctx.to_lang is None:
            return ctx, Reply(
                "Please select or send the language.",
                buttons=["EN", "UA", "ES", "FR", "DE", "PT"],
            )

    if (lang := to_language(text)) is not None:
        ctx = replace(ctx, to_lang=lang)

    if ctx.url is None:
        return Context(state=start), Reply("Please send me a link.")

    if text == "dub":
        duration = schedule(ctx, _dub(ctx.url), "Synthesize")
        return Context(state=start), Reply(
            f"Sure! I'll dub {ctx.url} in about {duration}."
        )

    if text == "srt":
        t = await transcript.load(ctx.url)
        with tempfile.TemporaryFile("w") as f:
            f.write(events_to_srt(t.events))
            f.flush()
            return Context(state=start), Reply("SRT", file=f.name)

    if text == "txt":
        t = await transcript.load(ctx.url)
        with tempfile.TemporaryFile("w") as f:
            f.write(
                "\n".join(
                    " ".join(chunk for chunk in event.chunks) for event in t.events
                )
            )
            f.flush()
            return Context(state=start), Reply("Plain text", file=f.name)

    if ctx.url and ctx.to_lang:
        duration = schedule(ctx, _translate(ctx.url, ctx.to_lang), "Translate")
        return Context(state=start), Reply(
            f"Sure! I'll dub {ctx.url} in about {duration}."
        )

    return ctx, None


async def dispatch(message: Message):
    sender_id: int = message.sender_id  # type: ignore

    if sender_id not in context:
        context[sender_id] = Context(state=start)

    ctx = context[sender_id]
    context[sender_id], reply = ctx.state(ctx, message)
    if reply:
        await send_message(ctx, reply)


@client.on(events.NewMessage(pattern=r".*"))
async def event_handler(event):
    if event.raw_text == "/start":
        await event.reply(
            f"Welcome to Freespeech! I am here to help you with video transcription, translation and dubbing.\n{URL_SOLUTION_TEXT}"  # noqa: E501
        )
        return

    if event.raw_text == "/reset":
        context[event.sender_id] = Context(state=start)
        await event.reply("Alright! Let's start over again.")
        return

    await dispatch(event)


@client.on(events.CallbackQuery())
async def handle_callback(event):
    await dispatch(event)


if __name__ == "__main__":
    logger.info("Starting Telegram client")
    client.start()
    client.run_until_disconnected()
