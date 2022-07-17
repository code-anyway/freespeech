import asyncio
import logging

import pytest

import freespeech.api.telegram as telegram_api

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_telegram_webhook_ratelimit():
    async def _install_webhook(message: str):
        logger.info(f"Executing {message}")
        assert isinstance(message, str)
        await telegram_api.bot.set_webhook("https://localhost.com")

    call_with_retries = telegram_api.handle_ratelimit(_install_webhook)

    await asyncio.gather(*[call_with_retries(f"Sample {i}") for i in range(1, 4)])
