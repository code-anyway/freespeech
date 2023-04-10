#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import io
import logging
import logging.config
import re
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Literal

import discord
from discord import Message

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
        "discord": {"level": logging.INFO, "handlers": logging_handler},
        "freespeech": {"level": logging.INFO, "handlers": logging_handler},
        "aiohttp": {"level": logging.INFO, "handlers": logging_handler},
        "__main__": {"level": logging.INFO, "handlers": logging_handler},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


URL_SOLUTION_TEXT = "Please send me a link to a YouTube video or Google Docs transcript or upload a video/audio here directly."  # noqa: E501


ParagraphSize = Literal["Small", "Medium", "Large", "Auto"]


@dataclass(frozen=True)
class Context:
    state: Callable
    message: Message | None = None
    from_lang: Language | None = None
    to_lang: Language | None = None
    method: SpeechToTextBackend | None = None
    url: str | None = None
    size: ParagraphSize | None = None


@dataclass(frozen=True)
class Reply:
    message: str
    data: bytes | None = None
    buttons: list[str] | None = None


class Button(discord.ui.Button):
    def __init__(self, label: str):
        super().__init__(label=label)

    async def callback(self, interaction: discord.Interaction):
        assert self.label is not None, "Button label is None"
        await interaction.response.defer()
        await dispatch(interaction.user.id, self.label)


context: dict[int, Context] = {}


def log_user_action(ctx: Context, action: str, **kwargs):
    sender = ctx.message.author if ctx.message else "Unknown"
    logger.info(f"User {sender} {action} {kwargs}")


def to_language(lang: str) -> Language | None:
    """Converts human readable language name to BCP 47 tag."""
    lang = lang.strip().lower()
    if lang in ("ru", "russian", "русский", "ru-RU"):
        return "ru-RU"
    elif lang in ("ua", "ukrainian", "українська", "украинский" "uk-ua"):
        return "uk-UA"
    elif lang in ("en", "english", "английский", "en-us"):
        return "en-US"
    elif lang in ("es", "spanish", "испанский", "español", "es-es"):
        return "es-ES"
    elif lang in ("fr", "french", "французский", "français", "fr-fr"):
        return "fr-FR"
    elif lang in ("de", "german", "немецкий", "deutsch", "de-de"):
        return "de-DE"
    elif lang in ("pt", "portuguese", "португальский", "português", "pt-pt"):
        return "pt-PT"
    elif lang in (
        "br",
        "brasilian",
        "бразильский",
        "brasileira",
        "brasileiro",
        "pt-br",
    ):  # noqa: E501
        return "pt-BR"
    elif lang in ("tr", "turkish", "tr-tr", "турецкий", "türkçe"):
        return "tr-TR"
    elif lang in ("se", "sv", "swedish", "шведский", "svenska", "sv-se"):
        return "sv-SE"
    elif lang in ("it", "italian", "итальянский", "italiano", "it-it"):
        return "it-IT"
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
            metric = (await youtube.get_meta(url)).duration_ms
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
            return round(metric / 1000 + metric / 2581)
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


async def send_message(message: Message | None, reply: Reply):
    assert message is not None
    buttons = [Button(label=button) for button in reply.buttons or []]
    if buttons:
        view = discord.ui.View()
        for button in buttons:
            view.add_item(button)
    else:
        view = None

    # create in-memory file out of reply.data
    if reply.data and ((extension := reply.message.lower()) in ("srt", "txt")):
        file = discord.File(
            fp=io.BytesIO(reply.data), filename=f"subtitles.{extension}"
        )
    else:
        file = None

    await message.reply(
        content=reply.message,
        view=view,
        file=file,
    )


async def schedule(ctx: Context, task: Awaitable, operation: Operation) -> str:
    assert ctx.url is not None

    async def execute_and_notify():
        try:
            log_user_action(ctx, action=operation, context=ctx)
            message = await task
        except (ValueError, NotImplementedError, PermissionError) as e:
            message = str(e)
        except Exception as e:
            logger.exception(e)
            message = "Something went wrong. Please try again later."

        await send_message(ctx.message, Reply(message))

    asyncio.create_task(execute_and_notify())

    return (
        seconds_to_human_readable(await estimate_operation_duration(ctx.url, operation))
        if platform(ctx.url) != "GCS"
        else "some time"
    )


async def _dub(url: str):
    media_url = await synthesize.dub(await transcript.load(source=url), is_smooth=True)
    return f"Here you are: {media_url}"


async def _translate(url: str, lang: Language):
    transcript_url = await translate.translate(
        source=url, lang=lang, format="SSMD-NEXT", platform="Google"
    )
    return f"Here you are: {transcript_url}. Paste this link into this chat to dub."


async def _transcribe(
    url: str,
    lang: Language,
    backend: SpeechToTextBackend,
    size: ParagraphSize,
) -> str:
    t = await transcribe.transcribe(url, lang=lang, backend=backend)
    # NOTE: Bill seems to be the most popular. Doing this here because changing the
    # default in the library would break existing code.
    events = [
        replace(event, voice=replace(event.voice, character="Bill"))
        for event in t.events
    ]

    match (size):
        case "Small":
            window_size_ms = 0
        case "Medium":
            window_size_ms = 30_000
        case "Large":
            window_size_ms = 60_000
        case "Auto":
            window_size_ms = 0
        case x:
            assert_never(x)

    t = replace(
        t,
        events=transcript.compress(events, window_size_ms=window_size_ms),
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
        text = str(message.content)
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

    ctx = replace(ctx, url=url, message=message)
    match _platform:
        case "YouTube":
            return replace(ctx, state=media_operation), Reply(
                "Create transcript using Subtitles or Speech Recognition?",
                buttons=["Subtitles", "Speech Recognition"],
            )
        case "GCS":
            return replace(ctx, state=media_operation), Reply(
                "Create transcript using Speech Recognition?",
                buttons=["Yes"],
            )
        case "Google" | "Notion":
            return replace(ctx, state=transcript_operation), Reply(
                "Would you like to translate, dub, or download the transcript as SRT or TXT?",  # noqa: E501
                buttons=["Translate", "Dub", "SRT", "TXT"],
            )
        case x:
            assert_never(x)


async def media_operation(
    ctx: Context, message: Message | str
) -> tuple[Context, Reply | None]:
    if not isinstance(message, str):
        text = str(message.content)
    else:
        text = message

    if text in ("Subtitles", "Speech Recognition", "Yes"):
        ctx = replace(
            ctx, method="Machine D" if text in ("Speech Recognition", "Yes") else text
        )

    if (lang := to_language(text)) is not None:
        ctx = replace(ctx, from_lang=lang)

    if text in ("Small", "Medium", "Large", "Auto"):
        ctx = replace(ctx, size=text)

    if ctx.method is None:
        return ctx, Reply(
            "Please select a method.", buttons=["Subtitles", "Speech Recognition"]
        )

    if ctx.from_lang is None:
        return ctx, Reply(
            "Please select *source* language. Or send it as a message.",
            buttons=["EN", "UA", "ES", "FR", "DE", "PT", "TR", "IT"],
        )

    if ctx.size is None:
        return ctx, Reply(
            "What size do you want timed paragraphs to be?",
            buttons=["Small", "Medium", "Large", "Auto"],
        )

    if ctx.url and ctx.from_lang and ctx.method and ctx.size:
        duration = await schedule(
            ctx, _transcribe(ctx.url, ctx.from_lang, ctx.method, ctx.size), "Transcribe"
        )
        return Context(state=start), Reply(
            f"Sure! Give me {duration} to transcribe it in {ctx.from_lang} using {ctx.method}.",  # noqa: E501
        )

    return ctx, None


async def transcript_operation(
    ctx: Context, message: Message | str
) -> tuple[Context, Reply | None]:
    if not isinstance(message, str):
        text = str(message.content)
    else:
        text = message
    text = text.strip().lower()

    if text == "translate":
        if ctx.to_lang is None:
            return ctx, Reply(
                "Please select *target* language. Or send it as a message.",
                buttons=["EN", "UA", "ES", "FR", "DE", "PT", "TR", "IT"],
            )

    if (lang := to_language(text)) is not None:
        ctx = replace(ctx, to_lang=lang)

    if ctx.url is None:
        return Context(state=start), Reply("Please send me a link.")

    if text == "dub":
        duration = await schedule(ctx, _dub(ctx.url), "Synthesize")
        return Context(state=start), Reply(f"Sure! I'll dub it in about {duration}.")

    def remove_pauses(s: str) -> str:
        return re.sub(r"#\d+(\.\d+)?#", "", s)

    if text == "srt":
        t = await transcript.load(ctx.url)
        data = remove_pauses(
            events_to_srt([event for event in t.events if "".join(event.chunks)])
        ).encode("utf-8")
        return Context(state=start), Reply("SRT", data=data)

    if text == "txt":
        t = await transcript.load(ctx.url)
        data = remove_pauses(
            "\n".join(
                text
                for event in t.events
                if (text := " ".join(chunk for chunk in event.chunks))
            )
        ).encode("utf-8")
        return Context(state=start), Reply("txt", data=data)

    if ctx.url and ctx.to_lang:
        duration = await schedule(ctx, _translate(ctx.url, ctx.to_lang), "Translate")
        return Context(state=start), Reply(
            f"Sure! I'll translate it in about {duration}."
        )

    return ctx, None


async def dispatch(sender_id: int, message: Message | str):
    if sender_id not in context:
        context[sender_id] = Context(state=start)

    ctx = context[sender_id]
    context[sender_id], reply = await ctx.state(ctx, message)
    if reply:
        msg = context[sender_id].message or ctx.message
        if msg is not None:
            await send_message(msg, reply)
        else:
            await message.reply(reply.message)  # type: ignore


if __name__ == "__main__":
    logger.info("Starting Discord client")
    bot_token = env.get_discord_bot_token()

    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logging.info(f"logged in as {client.user}")

    @client.event
    async def on_message(message: Message):
        if message.author == client.user:
            return

        if not client.user:
            return

        mention_ids = [user.id for user in message.mentions]
        # ignore messages that don't mention the bot or are not DMs
        if (client.user.id not in mention_ids) and not isinstance(
            message.channel, discord.DMChannel
        ):
            return

        if message.content == "/start":
            await message.reply(
                f"Welcome to Freespeech! I am here to help you with video transcription, translation and dubbing.\n{URL_SOLUTION_TEXT}"  # noqa: E501
            )
            return

        if message.content == "/reset":
            context[message.author.id] = Context(state=start)
            await message.reply("Alright! Let's start over again.")
            return

        await dispatch(message.author.id, message)

    client.run(bot_token, log_handler=None)
