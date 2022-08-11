import asyncio
import logging
from typing import Dict
from urllib.parse import urlparse

import aiogram as tg
from aiogram import types as tg_types
from aiogram.utils.exceptions import RetryAfter
from aiogram.utils.executor import start_webhook
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.client import chat, client, tasks, transcript
from freespeech.types import Error, assert_never

CLIENT_TIMEOUT = 1800

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
            return await func(*args, **kwargs)
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


def _log_extras(
    msg: tg_types.Message | None, error: Error | Exception | None = None
) -> Dict:
    """
    Prepares metadata from structured logging.
    Args:
        msg: telegram message to relate to

    Returns:
        ready object ot put to `extra` field of the logger to show up properly on
        Google logging

    """
    extras: Dict = {
        "labels": {"interface": "conversation_telegram"},
        "json_fields": {
            "client": "telegram_1",
            "user_id": msg.from_user.id if msg else None,
            "username": msg.from_user.username if msg else None,
            "full_name": msg.from_user.full_name if msg else None,
            "request": msg.text if msg else None,
        },
    }
    if error is not None:
        extras["error_details"] = str(error)
    return extras


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

    logger.info(
        f"user_says: {message.text}",
        extra=_log_extras(message),
    )

    session = client.create()

    result = await chat.ask(
        message=message.text, intent=None, state={}, session=session
    )
    logger.info("chat_ask", extra={"json_fields": {"result": pydantic_encoder(result)}})

    try:
        sent_message = await message.answer(
            result.message, disable_web_page_preview=True
        )
        logger.info(
            "message_answer", extra={"json_fields": {"result": str(sent_message)}}
        )
    except Exception as e:
        logger.error(f"Couldn't reply to TG message: {str(e)}")
        return

    match result:
        case tasks.Task():
            transcript_ready = await tasks.future(result, session)
            if isinstance(transcript_ready, Error):
                error = transcript_ready
                await _handle_error(message, error)
                return

            assert result.operation is not None
            match result.operation:
                case "Transcribe" | "Translate":
                    response = await transcript.save(
                        transcript_ready,
                        method="Google",
                        location=None,
                        session=session,
                    )
                    if isinstance(response, Error):
                        await _handle_error(message, response)
                        return

                    save_result = await tasks.future(response, session)
                    if isinstance(save_result, Error):
                        await _handle_error(message, save_result)
                        return

                    await _handle_success(f"Here you are: {save_result.url}", message)
                case "Synthesize":
                    link = transcript_ready.video or transcript_ready.audio
                    await _handle_success(
                        f"Here you are: {link}",
                        message,
                    )
                case never:
                    assert_never(never)

        case Error():
            await _handle_error(message, result)


async def _handle_success(reply: str, message: tg_types.Message):
    logger.info(
        f"conversation_success: {reply}",
        extra=_log_extras(message),
    )
    await message.reply(reply)


async def _handle_error(
    msg: tg_types.Message | tg_types.Update | None, error: Exception | Error
):
    """
    Handler for both conversation errors and unhandled exceptions happening during the
    conversation. Makes sure to thoroughly log details and answer something to the user.
    Args:
        message: a telegram message object or an update
        error: a freespeech.types.Error for the case we know what happened or an
         Exception for the case we don't

    Returns:

    """
    if isinstance(msg, tg_types.Update):
        msg = msg.message

    logger.error(
        f"Error in user dialogue: {error}",
        exc_info=error if isinstance(error, Exception) else None,
        extra=_log_extras(msg, error),
    )

    try:
        if msg:
            if isinstance(error, Error):
                await _reply(msg, error.message)
            else:
                await _reply(
                    msg,
                    "Sorry! Something went wrong. I could not complete your request. "
                    "I will let the team know about it.",
                )
    except Exception as e:
        logger.error(
            "Got a chat exception, but could not answer the user",
            exc_info=e,
            extra=_log_extras(msg, e),
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
    dispatcher.register_errors_handler(_handle_error)

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
