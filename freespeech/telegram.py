#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telethon import Button, TelegramClient, events

from freespeech import env
from freespeech.api import synthesize, transcribe, transcript, translate

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


@client.on(events.CallbackQuery())
async def handle_callback(event):
    action = event.data.decode("ASCII")

    if action == "dub":
        url = user_state[event.sender_id]
        await event.reply(f"Dubbing {url}. Please wait a few minutes.")
        media_url = await synthesize.synthesize(await transcript.load(source=url))
        await event.reply(f"Here you are: {media_url}")
    elif action == "translate":
        await select_language(event, action, "What language to translate to?")
    elif action in ("subtitles", "speech_recognition"):
        await select_language(event, action, "What's the original language?")
    elif action.startswith("translate;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await event.reply(f"Translating to {lang}. Stay tuned!")
        transcript_url = await translate.translate(
            source=url, lang=lang, format="SSMD-NEXT", platform="Google"
        )
        await event.reply(
            f"Here you are: {transcript_url}. Now you can paste this link into this chat to dub.",  # noqa: E501
            link_preview=False,
        )
    elif action.startswith("subtitles;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await event.reply(f"Transcribing in {lang} using Subtitles. Watch this space!")
        transcript_url = await transcript.save(
            transcript=await transcribe.transcribe(url, lang, "Subtitles"),
            platform="Google",
            format="SSMD-NEXT",
            location=None,
        )
        await event.reply(
            f"Here you are: {transcript_url}. Now you can paste this link into this chat to translate or dub.",  # noqa: E501
            link_preview=False,
        )
    elif action.startswith("speech_recognition;"):
        _, lang = action.split(";")
        url = user_state[event.sender_id]
        await event.reply(
            f"Transcribing in {lang} using speech recognition. Watch this space!"
        )
        transcript_url = await transcript.save(
            transcript=await transcribe.transcribe(url, lang, "Machine D"),
            platform="Google",
            format="SSMD-NEXT",
            location=None,
        )
        await event.reply(
            f"Here you are: {transcript_url}. Now you can paste this link into this chat to translate or dub.",  # noqa: E501
            link_preview=False,
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

    if url.startswith("https://docs.google.com/document/d/"):
        user_state[event.sender_id] = url
        await event.reply(
            "Translate or dub?",
            buttons=[
                Button.inline("Translate", data="translate".encode("ASCII")),
                Button.inline("Dub", data="dub".encode("ASCII")),
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
    client.start()
    client.run_until_disconnected()
