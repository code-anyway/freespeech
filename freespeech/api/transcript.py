from fastapi import APIRouter

from freespeech.lib import gdocs, notion
from freespeech.types import (
    Transcript,
    TranscriptFormat,
    TranscriptPlatform,
    assert_never,
)

router = APIRouter()


def _platform(source: str) -> TranscriptPlatform:
    if source.startswith("https://docs.google.com/document/d/"):
        return "Google"
    if source.startswith("https://www.notion.so/"):
        return "Notion"
    else:
        raise ValueError(f"Unsupported url: {source}")


@router.get("/transcript/{source}")
async def load(
    source: str,
) -> Transcript:
    platform = _platform(source)
    match platform:
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
