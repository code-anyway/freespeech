from dataclasses import replace
from pathlib import Path

import pytest

from freespeech.api import transcript

NOTION_TRANSCRIPT_DATABASE_ID = "e1a094dbac5845409d2e995d4ce3675e"


@pytest.mark.asyncio
async def test_save() -> None:
    from_srt = await transcript.load(
        source=Path("tests/lib/data/transcript/karlsson.srt"),
        lang="en-US",
    )
    from_srt = replace(from_srt, title="test_save")

    result = await transcript.save(
        transcript=from_srt,
        platform="Google",
        format="SRT",
        location=None,
    )
    assert result.startswith("https://docs.google.com/document/d/")

    result = await transcript.save(
        transcript=from_srt,
        platform="Google",
        format="SSMD",
        location=None,
    )
    assert result.startswith("https://docs.google.com/document/d/")

    response = await transcript.save(
        transcript=from_srt,
        platform="Notion",
        format="SSMD",
        location=NOTION_TRANSCRIPT_DATABASE_ID,
    )
    assert response.startswith("https://www.notion.so/test_save")
