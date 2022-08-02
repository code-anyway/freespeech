from dataclasses import replace

import pytest

from freespeech.client import client, tasks, transcript
from freespeech.types import Error

NOTION_TRANSCRIPT_DATABASE_ID = "e1a094dbac5845409d2e995d4ce3675e"


@pytest.mark.asyncio
async def test_save(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        with open("tests/lib/data/transcript/karlsson.srt", "rb") as stream:
            task = await transcript.load(
                source=stream, method="SRT", lang="en-US", session=session
            )
            from_srt = await tasks.future(task)
            from_srt = replace(from_srt, title="test_save")

        if isinstance(from_srt, Error):
            assert False, from_srt.message

        response = await transcript.save(
            from_srt, method="SRT", location=None, session=session
        )
        if isinstance(response, Error):
            assert False, response.message
        result = await tasks.future(response)
        if isinstance(result, Error):
            assert False, result.message
        assert result.url.startswith("https://docs.google.com/document/d/")

        response = await transcript.save(
            from_srt, method="Google", location=None, session=session
        )
        if isinstance(response, Error):
            assert False, response.message
        result = await tasks.future(response)
        if isinstance(result, Error):
            assert False, result.message
        assert result.url.startswith("https://docs.google.com/document/d/")

        response = await transcript.save(
            from_srt,
            method="Notion",
            location=NOTION_TRANSCRIPT_DATABASE_ID,
            session=session,
        )
        if isinstance(response, Error):
            assert False, response.message
        result = await tasks.future(response)
        if isinstance(result, Error):
            assert False, result.message
        assert result.url.startswith("https://www.notion.so/test_save")
