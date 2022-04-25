import asyncio
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from freespeech.lib import notion
from freespeech.types import Event, Meta, Voice

TRANSCRIPT_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"

SHORT_EVENT_1_EN = Event(time_ms=1001, duration_ms=1000, chunks=["One hen. Two ducks."])
SHORT_EVENT_2_EN = Event(
    time_ms=4001, duration_ms=2000, chunks=["Three squawking geese."]
)

SHORT_EVENT_1_RU = Event(
    time_ms=1001, duration_ms=1000, chunks=["Одна курица. Две утки."]
)
SHORT_EVENT_2_RU = Event(time_ms=4001, duration_ms=2000, chunks=["Два кричащих гуся."])


def test_parse_event():
    parse = notion.parse_time_interval

    assert parse("00:00:00.000/00:00:00.000") == (0, 0)
    assert parse(" 00:00:00.000 / 00:00:00.000 ") == (0, 0)
    assert parse("00:00:00.001/00:00:00.120") == (1, 119)
    assert parse("00:00:01.001/00:00:02.120") == (1001, 1119)
    assert parse("00:01:02.001/00:01:20.123") == (62001, 18122)
    assert parse("01:01:01.123/01:01:01.123") == (3661123, 0)


@pytest.mark.asyncio
async def test_create_update_get_transcript():
    # PAGE_ID = "cfe33f84267f43ec8f5c7e46b2daf0be"
    TEST_TRANSCRIPT = notion.Transcript(
        title="Test Transcript",
        origin="https://",
        lang="en-US",
        source="Subtitles",
        events=[SHORT_EVENT_1_EN, SHORT_EVENT_2_EN],
        voice=Voice(character="Alan Turing", pitch=1.0),
        weights=(2, 10),
        meta=Meta(title="Foo", description="Bar", tags=["one", "two"]),
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        dub_url="https://dub",
        clip_id="uuid",
        _id=None,
    )
    transcript = await notion.put_transcript(TRANSCRIPT_DATABASE_ID, TEST_TRANSCRIPT)
    assert transcript == replace(TEST_TRANSCRIPT, _id=transcript._id)
    assert await notion.get_transcript(transcript._id) == transcript

    TEST_TRANSCRIPT_UPDATED = notion.Transcript(
        title="Test Transcript Updated",
        origin="https://Updated",
        lang="ru-RU",
        source="Translate",
        events=[SHORT_EVENT_1_RU, SHORT_EVENT_2_RU],
        voice=Voice(character="Grace Hopper", pitch=2.0),
        weights=(3, 30),
        meta=Meta(
            title="Updated Foo", description="Updated Bar", tags=["three", "four"]
        ),
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        dub_url="https://dub/updated",
        clip_id="uuid-updated",
        _id=transcript._id,
    )
    transcript = await notion.put_transcript(
        TRANSCRIPT_DATABASE_ID, TEST_TRANSCRIPT_UPDATED
    )
    assert transcript == TEST_TRANSCRIPT_UPDATED
    assert await notion.get_transcript(transcript._id) == transcript
    # Avoid unclosed transport ResourceWarning.
    # details: https://docs.aiohttp.org/en/stable/client_advanced.html?highlight=graceful%20shutdown#graceful-shutdown  # noqa E501
    await asyncio.sleep(0.250)
