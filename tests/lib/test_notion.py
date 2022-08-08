import asyncio
from dataclasses import replace

import pytest
from test_transcript import EXPECTED_TRANSCRIPT

from freespeech.lib import notion

TRANSCRIPT_DATABASE_ID = "e1a094dbac5845409d2e995d4ce3675e"


@pytest.mark.asyncio
async def test_load():
    url = "https://www.notion.so/e1a094dbac5845409d2e995d4ce3675e?v=701419127df04d37a11d19491ad7d06d&p=a0b8986a76b541e997a5a2b6c792abc2"  # noqa E501
    expected_transcript = replace(
        EXPECTED_TRANSCRIPT, title="[DO NOT DELETE] test_read_transcript()"
    )

    transcript = await notion.load(url)

    assert transcript == expected_transcript


@pytest.mark.asyncio
async def test_create():
    expected_transcript = replace(
        EXPECTED_TRANSCRIPT, title="[DELETE ME] test_create_update_get_transcript()"
    )

    id, url, transcript = await notion.create(
        expected_transcript, database_id=TRANSCRIPT_DATABASE_ID
    )

    assert url.startswith("https://www.notion.so/")
    assert id.replace("-", "") in url
    assert transcript == expected_transcript
    assert await notion.get_transcript(id) == transcript
    # Avoid unclosed transport ResourceWarning.
    # details: https://docs.aiohttp.org/en/stable/client_advanced.html?highlight=graceful%20shutdown#graceful-shutdown  # noqa E501
    await asyncio.sleep(0.250)
