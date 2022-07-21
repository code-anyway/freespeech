import asyncio
import logging
from urllib.parse import urlparse

import aiogram as tg
import aiohttp
from aiogram import types as tg_types
from aiogram.utils.exceptions import RetryAfter
from aiogram.utils.executor import start_webhook
from aiohttp import ClientResponseError

from freespeech import client, env
from freespeech.api.chat import DUB_CLIENT_TIMEOUT

logger = logging.getLogger(__name__)

help_text = (
    "Hi, I am the Freespeech chat bot. I can transcribe, translate "
    "and dub videos into other languages.\n"
    "You send me instructions, and I take care of them. Let’s get started!\n"
    "First, send me a message to transcribe your video in the original language using "
    "the source you choose (audio or subtitles), like this:\n\n"
    "```\n"
    "Transcribe https://www.youtube.com/watch?v=N9B59PHIFbA "
    "in English using Machine A\n"
    "```\n"
    "I will send you a Google doc with the transcription for you to edit and approve. "
    "Then, send me the instruction to translate the doc to the language you like:\n\n"
    "```\n"
    "Translate https://docs.google.com/document/d/"
    "1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit to Ukrainian\n"
    "```\n"
    "Please check the translation - it might be inaccurate! And then, tell me to give "
    "it a voice, like this:\n\n"
    "```\n"
    "dub https://docs.google.com/document/d/"
    "1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit#\n"
    "```\n"
    "And I will send you a link to the dubbed video.\n"
    "Type /help to resend these instructions at any time. For quality purposes, all "
    "conversations are recorded. Enjoy!"
)

walkthrough_text = (
    "Also, check out a " "[quick walkthrough](https://youtu.be/3rCE5_OxuUo)."
)

MAX_RETRIES = 5


def get_chat_client():
    return aiohttp.ClientSession(
        base_url=env.get_chat_service_url(),
        timeout=aiohttp.ClientTimeout(DUB_CLIENT_TIMEOUT),
    )


def handle_ratelimit(func):
    """Decorator which handles the `RetryAfter` exception raised by telegram on
    rate limiting.
    """

    async def wrapper(*args, retries: int = MAX_RETRIES, **kwargs):
        if retries <= 0:
            raise RuntimeError(
                f"Could not complete after {MAX_RETRIES} retries. Halting."
            )
        try:
            await func(*args, **kwargs)
        except RetryAfter as e:
            logger.info(f"Telegram rate limit detected, waiting for {e.timeout}s")
            await asyncio.sleep(e.timeout)
            await wrapper(*args, retries=retries - 1, **kwargs)

    return wrapper


@handle_ratelimit
async def _answer(message: tg_types.Message, text: str, **kwargs):
    await message.answer(text, **kwargs)


@handle_ratelimit
async def _reply(message: tg_types.Message, text: str, **kwargs):
    await message.reply(text, **kwargs)


# not using aiogram decorators to have full control over order of rules
async def _help(message: tg_types.Message):
    await _answer(
        message, help_text, disable_web_page_preview=True, parse_mode="Markdown"
    )
    await _answer(
        message, walkthrough_text, disable_web_page_preview=False, parse_mode="Markdown"
    )


async def _is_message_for_bot(message: tg_types.Message) -> bool:
    if message.chat.type == "private":
        return True
    if "@" in message.text:
        bot_details = await message.bot.get_me()
        if f"@{bot_details.username}" in message.text:
            return True
    return False


async def _handle_message(message: tg_types.Message):
    """
    Conversation's entry point
    """
    if not await _is_message_for_bot(message):
        return

    async with get_chat_client() as _client:
        try:
            logger.info(
                f"user_says: {message.text}",
                extra={
                    "labels": {"interface": "conversation_telegram"},
                    "json_fields": {
                        "client": "telegram_1",
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "full_name": message.from_user.full_name,
                        "text": message.text,
                    },
                },
            )

            text, result, state = await client.say(_client, message.text)

            logger.info(
                f"conversation_success: {text}",
                extra={
                    "labels": {"interface": "conversation_telegram"},
                    "json_fields": {
                        "client": "telegram_1",
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "full_name": message.from_user.full_name,
                        "request": message.text,
                        "reply": text,
                        "result": result,
                        "state": state,
                    },
                },
            )

            await _reply(message, text)
        except ClientResponseError as e:
            logger.error(
                f"conversation_error: {e.message}",
                extra={
                    "labels": {"interface": "conversation_telegram"},
                    "json_fields": {
                        "client": "telegram_1",
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "full_name": message.from_user.full_name,
                        "request": message.text,
                        "error_details": str(e),
                    },
                },
            )
            await _reply(
                message,
                e.message,
                parse_mode="Markdown",
            )


def start_bot(port: int):
    webhook_route = urlparse(env.get_telegram_webhook_url()).path

    bot = tg.Bot(token=env.get_telegram_bot_token())
    dispatcher = tg.Dispatcher(bot)

    # order is important here, think of it as a filter chain.
    dispatcher.register_message_handler(
        dispatcher.async_task(_help), commands=["start", "help"]
    )
    dispatcher.register_message_handler(dispatcher.async_task(_handle_message))
    logger.info(f"Going to start telegram bot webhook on port {port}. ")

    start_webhook(
        dispatcher=dispatcher,
        webhook_path=webhook_route,
        on_shutdown=on_shutdown,
        on_startup=on_startup,
        port=port,
    )


async def set_commands_list_menu(disp):
    await disp.bot.set_my_commands(
        [
            tg_types.BotCommand("start", "Start"),
            tg_types.BotCommand("help", "Help"),
            tg_types.BotCommand("transcribe", "Transcribe"),
            tg_types.BotCommand("translate", "Translate"),
            tg_types.BotCommand("dub", "Dub"),
        ]
    )


async def on_startup(dispatcher):
    @handle_ratelimit
    async def _set_webhook(url: str):
        await dispatcher.bot.set_webhook(url)

    logger.info("Setting up telegram bot...")
    await set_commands_list_menu(dispatcher)
    await _set_webhook(env.get_telegram_webhook_url())

    logger.info("Telegram bot set up. ")


async def on_shutdown(dispatcher):
    # The webhook is not unset on a purpose. In a multi-node environment,
    # such as Google Cloud Run, having the webhook deregister in on_shutdown
    # would lead to a situation when the entire webhook stops receiving Telegram
    # updates, even if a single container was decommissioned.
    logger.info("Shutting down telegram bot... ")
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    logger.info("Telegram bot shut down.")
