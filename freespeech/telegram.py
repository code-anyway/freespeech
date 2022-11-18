#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import logging.config

from telethon import Button, TelegramClient, events

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate
from freespeech.types import Language, SpeechToTextBackend

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
    logger.info(f"User {event.sender_id} ({event.sender.username}) {action} {kwargs}")


async def handle_dub(url: str, is_smooth: bool, event):
    await event.reply(f"Dubbing {url}. Please wait a few minutes.")
    try:
        log_user_action(event, "dub", url=url, is_smooth=is_smooth)
        media_url = await synthesize.dub(
            await transcript.load(source=url), is_smooth=is_smooth
        )
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")
        return
    await event.reply(f"Here you are: {media_url}")


async def handle_translate(url: str, lang: Language, event):
    await event.reply(f"Translating to {lang}. Stay tuned!")
    try:
        log_user_action(event, "translate", url=url, lang=lang)
        transcript_url = await translate.translate(
            source=url, lang=lang, format="SSMD-NEXT", platform="Google"
        )
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")
        return
    await event.reply(
        f"Here you are: {transcript_url}. Now you can paste this link into this chat to dub.",  # noqa: E501
        link_preview=False,
    )


async def handle_transcribe(
    url: str, lang: Language, backend: SpeechToTextBackend, event
):
    await event.reply(f"Transcribing in {url} using {backend}. Watch this space!")
    try:
        log_user_action(event, "transcribe", url=url, lang=lang, backend=backend)
        transcript_url = await transcript.save(
            transcript=await transcribe.transcribe(url, lang=lang, backend=backend),
            platform="Google",
            format="SSMD-NEXT",
            location=None,
        )
    except Exception as e:
        logger.exception(e)
        await event.reply("Something went wrong. Please try again later.")
        return
    await event.reply(
        f"Here you are: {transcript_url}. Now you can paste this link into this chat to translate or dub.",  # noqa: E501
        link_preview=False,
    )


@client.on(events.CallbackQuery())
async def handle_callback(event):
    action = event.data.decode("ASCII")

    if action == "dub-1":
        url = user_state[event.sender_id]
        await handle_dub(url, is_smooth=False, event=event)
    if action == "dub-2":
        url = user_state[event.sender_id]
        await handle_dub(url, is_smooth=True, event=event)
    elif action == "translate":
        await select_language(event, action, "What language to translate to?")
    elif action in ("subtitles", "speech_recognition"):
        await select_language(event, action, "What's the original language?")
    elif action.startswith("translate;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await handle_translate(url, lang, event)
    elif action.startswith("subtitles;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await handle_transcribe(url, lang, "Subtitles", event)
    elif action.startswith("speech_recognition;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await handle_transcribe(url, lang, "Machine D", event)
    else:
        raise ValueError(f"Unknown action: {action}")


@client.on(events.NewMessage(pattern=r".*"))
async def url_handler(event):
    urls = [
        url for url in event.raw_text.split(" ") if url.strip().startswith("https://")
    ]

    if not urls:
        await event.reply(f"No links found in your message. {URL_SOLUTION_TEXT}")
        return

    url = urls[0]

    if url.startswith("https://docs.google.com/document/d/"):
        user_state[event.sender_id] = url
        await event.reply(
            "Translate or dub?",
            buttons=[
                Button.inline("Translate", data="translate".encode("ASCII")),
                Button.inline("Dub-1", data="dub-1".encode("ASCII")),
                Button.inline("Dub-2", data="dub-2".encode("ASCII")),
            ],
        )
    elif url.startswith("https://youtu.be/") or url.startswith(
        "https://www.youtube.com/"
    ):
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
    else:
        await event.reply(f"Unsupported url: {url}. {URL_SOLUTION_TEXT}")


if __name__ == "__main__":
    logger.info("Starting Telegram client")
    client.start()
    client.run_until_disconnected()
