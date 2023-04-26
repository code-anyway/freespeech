import asyncio

import pytest

from freespeech.api import transcribe
from freespeech.types import (
    SPEECH_BACKENDS,
    Transcript,
    Voice,
    is_speech_to_text_backend,
)


@pytest.mark.asyncio
async def test_load_subtitles() -> None:
    result = await transcribe.transcribe(
        source="https://youtu.be/bhRaND9jiOA",
        backend="Subtitles",
        lang="en-US",
    )

    first, *_ = result.events

    assert first.time_ms == 480
    assert first.chunks[0].startswith("one hen two ducks three squawking geese")
    assert first.duration_ms == 27920
    assert first.voice == Voice(character="Ada", pitch=0.0, speech_rate=1.0)

    assert result.audio
    assert result.audio.startswith("https://")
    assert result.audio.endswith(".webm")

    assert result.video
    assert result.video.startswith("https://")
    assert result.video.endswith(".mp4")


@pytest.mark.asyncio
async def test_transcribe() -> None:
    responses = [
        transcribe.transcribe(
            source="https://www.youtube.com/watch?v=bhRaND9jiOA",
            backend=backend,
            lang="en-US",
        )
        for backend in SPEECH_BACKENDS
        if is_speech_to_text_backend(backend)
    ]

    results: list[Transcript] = await asyncio.gather(*responses)

    for backend, result in zip(SPEECH_BACKENDS, results):
        assert result.source is not None, f"Backend {backend} failed"
        assert result.source.method == backend, f"Backend {backend} failed"
        assert result.audio is not None, f"Backend {backend} failed"
        assert result.audio.startswith("https://")
        assert result.audio.endswith(".webm")


@pytest.mark.asyncio
async def test_transcribe_machine_d() -> None:
    result = await transcribe.transcribe(
        source="https://www.youtube.com/watch?v=N9B59PHIFbA",
        lang="en-US",
        backend="Machine D",
    )
    assert result.title
    assert result.title.startswith("en-US")
    assert isinstance(result, Transcript)
    assert len(result.events) == 13
