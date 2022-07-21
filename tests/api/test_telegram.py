import asyncio
import logging
from typing import Dict

import pytest
from aiogram.utils.exceptions import RetryAfter

import freespeech.api.telegram as telegram_api

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_ratelimit_retry_decorator():
    attempt_count: Dict[str, int] = {}

    async def _install_webhook_mock(message: str):
        current_attempts = attempt_count.get(message, 0) + 1
        attempt_count[message] = current_attempts
        logger.info(f"Executing {message}, attempt {current_attempts}")

        if current_attempts > 3:
            # assume success after third attempt
            return
        else:
            raise RetryAfter(0.1)

    call_with_retries = telegram_api.handle_ratelimit(_install_webhook_mock)

    await asyncio.gather(*[call_with_retries(f"Sample {i}") for i in range(1, 4)])
