from pathlib import Path

from fastapi import APIRouter

from freespeech.lib import gdocs, notion
from freespeech.lib.transcript import srt_to_events
from freespeech.types import (
    Language,
    Source,
    Transcript,
    TranscriptFormat,
    TranscriptPlatform,
    assert_never,
    is_transcript_platform,
    platform,
)

router = APIRouter()


@router.get("/transcript")
async def load(source: str | Path, lang: Language | None = None) -> Transcript:
    if isinstance(source, Path):
        if lang is None:
            raise ValueError("lang must be specified when loading from a file")

        with open(source) as stream:
            return Transcript(
                source=Source(method="SRT", url=str(source)),
                events=srt_to_events(stream.read()),
                lang=lang,
            )

    transcript_platform = platform(source)
    if not is_transcript_platform(transcript_platform):
        raise ValueError(f"Unsupported platform: {transcript_platform}")

    match transcript_platform:
        case "Google":
            return gdocs.load(source)
        case "Notion":
            return await notion.load(source)
        case x:
            assert_never(x)


@router.post("/transcript")
async def save(
    transcript: Transcript,
    platform: TranscriptPlatform,
    format: TranscriptFormat,
    location: str | None,
) -> str:
    match platform:
        case "Notion":
            if location is None:
                raise ValueError("For Notion `location` should be set to Database ID.")
            _, url, _ = await notion.create(
                transcript, format=format, database_id=location
            )
            return url
        case "Google":
            return gdocs.create(transcript, format=format)
        case x:
            assert_never(x)
