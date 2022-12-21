#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import logging.config
import re
from dataclasses import dataclass, replace
from typing import Awaitable, Callable
from uuid import uuid4

from telethon import Button, TelegramClient, events, hints
from telethon.tl.custom.message import Message
from telethon.utils import get_display_name

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

logging_handler = ["google", "console"]

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


URL_SOLUTION_TEXT = (
    "Please send me a link to a YouTube video or Google Docs transcript."
)


@dataclass(frozen=True)
class Context:
    state: Callable
    user_id: int
    client: TelegramClient
    message: Message | None = None
    from_lang: Language | None = None
    to_lang: Language | None = None
    method: SpeechToTextBackend | None = None
    url: str | None = None


@dataclass(frozen=True)
class Reply:
    message: str
    file: hints.FileLike | None = None
    buttons: list[str] | None = None


context: dict[int, Context] = {}


def context_to_dict(ctx: Context) -> dict:
    return {
        "labels": {"interface": "telegram"},
        "json_fields": {
            "state": ctx.state.__name__,
            "user_id": ctx.user_id,
            "message": ctx.message.message if ctx and ctx.message else None,
            "from_lang": ctx.from_lang,
            "to_lang": ctx.to_lang,
            "method": ctx.method,
            "url": ctx.url,
        },
    }


def log_user_action(ctx: Context, action: str):
    sender_id = ctx.message.sender_id if ctx.message else "Unknown"
    sender = ctx.message.sender if ctx.message else None
    logger.info(
        f"User {sender_id} ({get_display_name(sender) if sender else 'Unknown'}) {action}",  # noqa: E501
        extra=context_to_dict(ctx),
    )


def to_language(lang: str) -> Language | None:
    """Converts human readable language name to BCP 47 tag."""
    lang = lang.strip().lower()
    if lang in ("ru", "russian", "русский", "ru-RU"):
        return "ru-RU"
    elif lang in ("ua", "ukrainian", "українська", "украинский" "uk-UA"):
        return "uk-UA"
    elif lang in ("en", "english", "английский", "en-US"):
        return "en-US"
    elif lang in ("es", "spanish", "испанский", "español", "es-ES"):
        return "es-ES"
    elif lang in ("fr", "french", "французский", "français", "fr-FR"):
        return "fr-FR"
    elif lang in ("de", "german", "немецкий", "deutsch", "de-DE"):
        return "de-DE"
    elif lang in ("pt", "portuguese", "португальский", "português", "pt-PT"):
        return "pt-PT"
    else:
        return None


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


async def send_message(
    client: TelegramClient, recipient_id: int, reply_to: Message | None, reply: Reply
):
    _buttons = [
        Button.inline(button, data=button.encode("ASCII"))
        for button in reply.buttons or []
    ]
    if reply_to:
        if reply.file:
            await reply_to.reply(
                message=reply.message,
                buttons=_buttons or None,
                file=reply.file,
                force_document=False,
                link_preview=False,
            )
        else:
            await reply_to.reply(
                message=reply.message,
                buttons=_buttons or None,
                force_document=False,
                link_preview=False,
            )
    else:
        if reply.file:
            await client.send_file(
                recipient_id,
                reply.file,
                caption=reply.message,
                buttons=_buttons or None,
                force_document=False,
                link_preview=False,
            )
        else:
            await client.send_message(
                recipient_id,
                message=reply.message,
                buttons=_buttons or None,
                force_document=False,
                link_preview=False,
            )


async def schedule(ctx: Context, task: Awaitable, operation: Operation) -> str:
    assert ctx.url is not None

    async def execute_and_notify():
        try:
            log_user_action(ctx, action=operation)
            message = await task
        except (ValueError, NotImplementedError, PermissionError) as e:
            message = str(e)
        except Exception as e:
            logger.exception(e)
            message = "Something went wrong. Please try again later."

        await send_message(
            client=ctx.client,
            recipient_id=ctx.user_id,
            reply_to=ctx.message,
            reply=Reply(message),
        )

    asyncio.create_task(execute_and_notify())

    return seconds_to_human_readable(
        await estimate_operation_duration(ctx.url, operation)
    )


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


async def start(ctx: Context, message: Message | str) -> tuple[Context, Reply | None]:
    if not isinstance(message, str):
        text = str(message.raw_text)
    else:
        text = message
    urls = [url for url in text.split(" ") if url.strip().startswith("https://")]

    if not urls:
        return ctx, Reply(f"{URL_SOLUTION_TEXT}")

    url = urls[0]

    try:
        _platform = platform(url)
    except ValueError as e:
        logger.exception(e)
        return ctx, Reply(str(e))

    # assert isinstance(message, Message)
    ctx = replace(ctx, url=url, message=message)
    match _platform:
        case "YouTube" | "GCS":
            return replace(ctx, state=media_operation), Reply(
                "Create transcript using Subtitles or Speech Recognition?",
                buttons=["Subtitles", "Speech Recognition"],
            )
        case "Google" | "Notion":
            return replace(ctx, state=transcript_operation), Reply(
                "Would you like to translate, dub, or download the transcript as SRT or TXT?",  # noqa: E501
                buttons=["Translate", "Dub", "SRT", "TXT"],
            )
        case x:
            assert_never(x)


def reset(ctx: Context) -> Context:
    return Context(state=start, user_id=ctx.user_id, client=ctx.client)


async def media_operation(
    ctx: Context, message: Message | str
) -> tuple[Context, Reply | None]:
    if not isinstance(message, str):
        text = str(message.raw_text)
    else:
        text = message

    if text in ("Subtitles", "Speech Recognition"):
        ctx = replace(ctx, method="Machine D" if text == "Speech Recognition" else text)

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
        duration = await schedule(
            ctx, _transcribe(ctx.url, ctx.from_lang, ctx.method), "Transcribe"
        )
        return reset(ctx), Reply(
            f"Sure! Give me {duration} to transcribe it in {ctx.from_lang} using {ctx.method}.",  # noqa: E501
        )

    return ctx, None


async def transcript_operation(
    ctx: Context, message: Message | str
) -> tuple[Context, Reply | None]:
    if not isinstance(message, str):
        text = str(message.raw_text)
    else:
        text = message
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
        return reset(ctx), Reply("Please send me a link.")

    if text == "dub":
        duration = await schedule(ctx, _dub(ctx.url), "Synthesize")
        return reset(ctx), Reply(f"Sure! I'll dub it in about {duration}.")

    def remove_pauses(s: str) -> str:
        return re.sub(r"#\d+(\.\d+)?#", "", s)

    if text == "srt":
        t = await transcript.load(ctx.url)
        filename = f"/tmp/{uuid4()}.srt"
        with open(filename, "wb") as f:
            data = remove_pauses(
                events_to_srt([event for event in t.events if "".join(event.chunks)])
            ).encode("utf-8")
            f.write(data)

        return reset(ctx), Reply("SRT", file=filename)

    if text == "txt":
        t = await transcript.load(ctx.url)
        filename = f"/tmp/{uuid4()}.txt"
        with open(filename, "wb") as f:
            data = remove_pauses(
                "\n".join(
                    text
                    for event in t.events
                    if (text := " ".join(chunk for chunk in event.chunks))
                )
            ).encode("utf-8")
            f.write(data)

        return reset(ctx), Reply("Plain text", file=filename)

    if ctx.url and ctx.to_lang:
        duration = await schedule(ctx, _translate(ctx.url, ctx.to_lang), "Translate")
        return reset(ctx), Reply(f"Sure! I'll translate it in about {duration}.")

    return ctx, None


async def dispatch(client: TelegramClient, sender_id: int, message: Message | str):
    if sender_id not in context:
        context[sender_id] = Context(state=start, user_id=sender_id, client=client)

    ctx = context[sender_id]
    context[sender_id], reply = await ctx.state(ctx, message)
    if reply:
        reply_to = context[sender_id].message or ctx.message
        if reply_to is not None:
            await send_message(client, sender_id, reply_to, reply)
        else:
            if isinstance(message, Message):
                await send_message(client, sender_id, message, reply)
            else:
                logger.warning("No message to reply to. Text: %s", reply.message)
                await send_message(client, sender_id, None, reply)


if __name__ == "__main__":
    logger.info("Starting Telegram client")
    api_id = env.get_telegram_api_id()
    api_hash = env.get_telegram_api_hash()

    with TelegramClient("/tmp/freespeechbot", api_id, api_hash).start(
        bot_token=env.get_telegram_bot_token()
    ) as client:

        @client.on(events.NewMessage(pattern=r".*"))
        async def event_handler(event):
            if event.raw_text == "/start":
                await event.reply(
                    f"Welcome to Freespeech! I am here to help you with video transcription, translation and dubbing.\n{URL_SOLUTION_TEXT}"  # noqa: E501
                )
                return

            if event.raw_text == "/reset":
                context[event.sender_id] = Context(
                    state=start, user_id=event.sender_id, client=client
                )
                await event.reply("Alright! Let's start over again.")
                return

            await dispatch(client, event.sender_id, event)

        @client.on(events.CallbackQuery())
        async def handle_callback(event):
            await dispatch(client, event.sender_id, event.data.decode("ASCII"))

        client.start()
        client.run_until_disconnected()
