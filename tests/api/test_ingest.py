import pytest

from freespeech.api import transcribe


@pytest.mark.asyncio
async def test_ingest_youtube_short() -> None:
    audio, video = await transcribe.ingest(
        "https://www.youtube.com/watch?v=hgV8mB-M9po"
    )

    assert audio
    assert audio.startswith("gs://")
    assert audio.endswith(".webm")

    assert video
    assert video.startswith("gs://")
    assert video.endswith(".webm")
