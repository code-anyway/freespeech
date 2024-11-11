import pytest

from freespeech.api import transcript
from freespeech.typing import Event, Voice


@pytest.mark.asyncio
async def test_load_srt_from_gdoc() -> None:
    from_gdoc = await transcript.load(
        source="https://docs.google.com/document/d/1-pexQIJLV_RFnPnjoMG76giKzPmItMnbf17N_nNCIKs/edit",  # noqa: E501
    )

    first, *_, last = from_gdoc.events
    assert first == Event(
        time_ms=8484,
        chunks=["Inspired by Astrid Lindgren's", "fairy", "tale."],
        duration_ms=5205,
        voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
    )
    assert last == Event(
        time_ms=15383,
        chunks=["Karlsson and The Kid"],
        duration_ms=4373,
        voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
    )


@pytest.mark.asyncio
async def test_load_ssmd_from_gdoc() -> None:
    transcript_from_ssmd = await transcript.load(
        source="https://docs.google.com/document/d/1Pf1LZEf_-HbgEDxvF7flEHws6yyXadkJ30a7DlKOQOg/edit",  # noqa: E501
    )

    assert transcript_from_ssmd.events == [
        Event(
            group=0,
            time_ms=0,
            chunks=["Hello #0.0# world! #1.0#"],
            duration_ms=2000,
            voice=Voice(character="Alan", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            group=0,
            time_ms=2000,
            chunks=["There are five pre-conditions for peace."],
            duration_ms=1000,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            group=1,
            time_ms=3000,
            chunks=["Hi!"],
            duration_ms=1000,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.2),
        ),
        Event(
            chunks=[""],
            time_ms=4000,
            duration_ms=2000,
            group=1,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.2),
        ),
        Event(
            group=1,
            time_ms=6000,
            chunks=["Hmm"],
            duration_ms=None,
            voice=Voice(character="Grace", pitch=0.0, speech_rate=2.0),
        ),
    ]
