import aiogram as tg
import aiohttp
from aiogram import types as tg_types
from aiohttp.abc import Application

from freespeech import client, env
from freespeech.api.chat import DUB_CLIENT_TIMEOUT

bot = tg.Bot(token=env.get_telegram_bot_token())
# TODO replace with env.configuration
SERVER_URL = "https://ce0b-178-74-255-76.eu.ngrok.io"
WEBHOOK_ROUTE = "/tg_webhook"
WEBHOOK_URL = f"{SERVER_URL}{WEBHOOK_ROUTE}"
dp = tg.Dispatcher(bot)


def get_chat_client():
    return aiohttp.ClientSession(
        base_url="http://localhost:8080",
        timeout=aiohttp.ClientTimeout(DUB_CLIENT_TIMEOUT),
    )


@dp.message_handler()
async def _message(message: tg_types.Message):
    """
    Conversation's entry point
    """
    async with get_chat_client() as _client:
        response = await client.say(_client, message.text)
        await message.reply(f"Got response from API: {response}")


def start_bot(webapp: Application):
    tg.executor.set_webhook(
        dp,
        webhook_path=WEBHOOK_ROUTE,
        web_app=webapp,
        on_shutdown=on_shutdown,
        on_startup=on_startup,
    )


async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(dp):
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()
