import logging

import aiogram as tg
import aiohttp
from aiogram import types as tg_types
from aiogram.utils.executor import start_webhook
from aiohttp import ClientResponseError

from freespeech import client, env
from freespeech.api.chat import DUB_CLIENT_TIMEOUT

logger = logging.getLogger(__name__)

help_text = [
    "Hi, I am a Freespeech chat bot.\n"
    "I can translate and dub videos to other languages.",
    "Try this:",
    "Transcribe https://www.youtube.com/watch?v=N9B59PHIFbA in English "
    "using Machine B",
    "It will give you a google doc to edit and approve.\n" "Then you can translate it:",
    "Translate https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit to Ukrainian",  # noqa: E501
    "Please, edit it as well. Translation might be inaccurate! And then give it a voice:",  # noqa: E501
    "dub https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit#",  # noqa: E501,
    "/help for this message anytime. For quality purposes this conversations are recorded.",  # noqa: E501,
]

bot = tg.Bot(token=env.get_telegram_bot_token())
WEBHOOK_ROUTE = "/tg_webhook"
WEBHOOK_URL = env.get_telegram_webhook_url()
dispatcher = tg.Dispatcher(bot)

bot_details: tg_types.User


def get_chat_client():
    return aiohttp.ClientSession(
        base_url=env.get_chat_service_url(),
        timeout=aiohttp.ClientTimeout(DUB_CLIENT_TIMEOUT),
    )


# not using aiogram decorators to have full control over order of rules
@dispatcher.async_task
async def _help(message: tg_types.Message):
    for s in help_text:
        await message.answer(s, disable_web_page_preview=True)


@dispatcher.async_task
async def _message(message: tg_types.Message):
    """
    Conversation's entry point
    """

    def _is_message_for_bot() -> bool:
        global bot_details
        if f"@{bot_details.username}" in message.text:
            return True
        if message.chat.type == "private":
            return True
        return False

    if not _is_message_for_bot():
        return

    async with get_chat_client() as _client:
        try:
            text, response, state = await client.say(_client, message.text)
            logger.warning(
                f"Conversation with {message.from_user.username}:\n"
                f"User: {message.text}\n"
                f"Bot:  {text}"
            )
            await message.reply(text)
        except ClientResponseError as e:
            logger.error(
                f"Error in conversation with {message.from_user.username}:\n"
                f"User: {message.text}\n"
                f"Bot:  {e.message}"
            )
            await message.reply(f"Error :{e.message}")


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


async def commands_list_menu(disp):
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
    await commands_list_menu(dispatcher)

    global bot_details
    bot_details = await bot.get_me()

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
