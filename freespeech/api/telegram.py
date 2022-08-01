import logging
from urllib.parse import urlparse

import aiogram as tg
import aiohttp
from aiogram import types as tg_types
from aiogram.utils.executor import start_webhook

from freespeech import env
from freespeech.client import chat, client, tasks
from freespeech.types import Error

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


bot = tg.Bot(token=env.get_telegram_bot_token())
WEBHOOK_URL = env.get_telegram_webhook_url()
WEBHOOK_ROUTE = urlparse(WEBHOOK_URL).path
dispatcher = tg.Dispatcher(bot)


# not using aiogram decorators to have full control over order of rules
@dispatcher.async_task
async def _help(message: tg_types.Message):
    await message.answer(
        help_text, disable_web_page_preview=True, parse_mode="Markdown"
    )
    await message.answer(
        walkthrough_text, disable_web_page_preview=False, parse_mode="Markdown"
    )


async def _is_message_for_bot(message: tg_types.Message) -> bool:
    if message.chat.type == "private":
        return True
    if "@" in message.text:
        bot_details = await bot.get_me()
        if f"@{bot_details.username}" in message.text:
            return True
    return False


@dispatcher.async_task
async def _message(message: tg_types.Message):
    """
    Conversation's entry point
    """
    if not await _is_message_for_bot(message):
        return

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

    result = await chat.ask(
        message=message.text, intent=None, state={}, session=client.create()
    )

    await message.reply(result.message, parse_mode="Markdown")
    match result:
        case tasks.Task():
            task_result = await tasks.future(result)
            logger.info(
                f"conversation_success: {task_result.message}",
                extra={
                    "labels": {"interface": "conversation_telegram"},
                    "json_fields": {
                        "client": "telegram_1",
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "full_name": message.from_user.full_name,
                        "request": message.text,
                        "reply": task_result.message,
                        "result": result,
                    },
                },
            )
            await message.reply(task_result.message)
        case Error():
            logger.error(
                f"conversation_error: {result.message}",
                extra={
                    "labels": {"interface": "conversation_telegram"},
                    "json_fields": {
                        "client": "telegram_1",
                        "user_id": message.from_user.id,
                        "username": message.from_user.username,
                        "full_name": message.from_user.full_name,
                        "request": message.text,
                        "error_details": result.details,
                    },
                },
            )


def start_bot(port: int):
    # order is important here, think of it as a filter chain.
    dispatcher.register_message_handler(_help, commands=["start", "help"])
    dispatcher.register_message_handler(_message)
    logger.warning(f"Going to start telegram bot webhook on port {port}. ")

    start_webhook(
        dispatcher=dispatcher,
        webhook_path=WEBHOOK_ROUTE,
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
    logger.warning("Setting up telegram bot...")
    await set_commands_list_menu(dispatcher)
    await bot.set_webhook(WEBHOOK_URL)
    logger.warning("Telegram bot set up. ")


async def on_shutdown(dispatcher):
    # The webook is not unset on a purpose. In a multi-node environment,
    # such as Google Cloud Run, having the webhook deregister in on_shutdown
    # would lead to a situation when the entire webhook stops receiving Telegram
    # updates, even if a single container was decommissioned.
    logger.warning("Shutting down telegram bot... ")
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    logger.warning("Telegram bot shut down.")
