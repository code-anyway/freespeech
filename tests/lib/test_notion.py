import asyncio
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from freespeech.lib import notion
from freespeech.types import (
    Audio,
    Event,
    Media,
    Meta,
    Settings,
    Source,
    Transcript,
    Video,
    Voice,
)

TRANSCRIPT_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"

SHORT_EVENT_1_EN = Event(
    time_ms=1001,
    duration_ms=1000,
    chunks=["One hen. Two ducks."],
    voice=Voice(character="Alonzo Church"),
)
LONG_EVENT_1_EN = Event(
    time_ms=4001,
    duration_ms=2000,
    chunks=["Three squawking geese. " * 100] + ["Bah"],
    voice=Voice(character="Alonzo Church"),
)

SHORT_EVENT_1_RU = Event(
    time_ms=1001,
    duration_ms=1000,
    chunks=["Одна курица. Две утки."],
    voice=Voice(character="Alonzo Church"),
)
LONG_EVENT_1_RU = Event(
    time_ms=4001,
    duration_ms=2000,
    chunks=["Два кричащих гуся." * 150] + ["Bah"],
    voice=Voice(character="Alonzo Church"),
)

EXPECTED_TRANSCRIPT = Transcript(
    title="[DO NOT DELETE] test_read_transcript()",
    source=Source(method="Subtitles", url="https://youtube"),
    lang="en-US",
    events=[
        Event(time_ms=1001, duration_ms=1000, chunks=["One hen. Two ducks."]),
        Event(
            time_ms=3000,
            duration_ms=2000,
            chunks=["Blah"],
            voice=Voice(character="Alonzo Church"),
        ),
        Event(
            time_ms=6001,
            duration_ms=1000,
            chunks=["Blah Blah"],
            voice=Voice(character="Alonzo Church"),
        ),
    ],
    audio=Media[Audio]("https://foobar", info=None),
    video=Media[Video]("https://barbaz", info=None),
    settings=Settings(original_audio_level=1),
)


@pytest.mark.asyncio
async def test_read_transcript():
    PAGE_ID = "4738b64bf29f4c98bfad98e8c2a6690a"
    transcript = await notion.get_transcript(PAGE_ID)

    assert transcript == EXPECTED_TRANSCRIPT


@pytest.mark.asyncio
async def test_create_update_get_transcript():
    # PAGE_ID = "cfe33f84267f43ec8f5c7e46b2daf0be"
    meta = Meta(title="Foo", description="Bar" * 700, tags=["one", "two"])
    TEST_TRANSCRIPT = notion.Transcript(
        title="Test Transcript",
        origin="https://",
        lang="en-US",
        source="Subtitles",
        events=[SHORT_EVENT_1_EN, LONG_EVENT_1_EN],
        voice=Voice(character="Alan Turing", pitch=1.0),
        weights=(2, 10),
        meta=meta,
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        dub_url="https://dub",
        clip_id="uuid",
        _id=None,
    )
    transcript = await notion.put_transcript(TRANSCRIPT_DATABASE_ID, TEST_TRANSCRIPT)
    assert transcript == replace(TEST_TRANSCRIPT, _id=transcript._id)
    assert await notion.get_transcript(transcript._id) == transcript

    meta_updated = Meta(
        title="Updated Foo", description="Updated Bar" * 200, tags=["three", "four"]
    )
    TEST_TRANSCRIPT_UPDATED = notion.Transcript(
        title="Test Transcript Updated",
        origin="https://Updated",
        lang="ru-RU",
        source="Translate",
        events=[SHORT_EVENT_1_RU, LONG_EVENT_1_RU],
        voice=Voice(character="Grace Hopper", pitch=2.0),
        weights=(3, 30),
        meta=meta_updated,
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
