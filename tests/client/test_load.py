import asyncio
from typing import Sequence

import pytest

from freespeech.client import client, tasks, transcript
from freespeech.types import Error, Event, Method, Voice


@pytest.mark.asyncio
async def test_load_srt(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    with open("tests/lib/data/transcript/fmj.srt", "rb") as stream:
        task = await transcript.load(
            source=stream, method="SRT", lang="en-US", session=session
        )
        result = await tasks.future(task)
        if isinstance(result, Error):
            assert False, result.message

        first, *_, last = result.events
        assert first == Event(
            time_ms=27110,
            chunks=['"America has heard the bugle call'],
            duration_ms=5050,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
        )
        assert last == Event(
            time_ms=6716480,
            chunks=["And I am not afraid."],
            duration_ms=1580,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0),
        )


@pytest.mark.asyncio
async def test_load_ssmd(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    with open("tests/lib/data/transcript/test.ssmd", "rb") as stream:
        task = await transcript.load(
            source=stream, method="SSMD", lang="en-US", session=session
        )
        result = await tasks.future(task)
        if isinstance(result, Error):
            assert False, result.message

        first, *_, last = result.events
        assert first == Event(
            time_ms=0,
            chunks=["Hello, Bill!", "How are you?"],
            duration_ms=1000,
            voice=Voice(character="Grace Hopper", pitch=0.0, speech_rate=1.0),
        )
        assert last == Event(
            time_ms=2000,
            chunks=["It was a huge mistake."],
            duration_ms=None,
            voice=Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.4),
        )


@pytest.mark.asyncio
async def test_load_subtitles(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    task = await transcript.load(
        source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
        method="Subtitles",
        lang="en-US",
        session=session,
    )

    result = await tasks.future(task)
    if isinstance(result, Error):
        assert False, result.message

    first, *_, last = result.events

    assert first.time_ms == 0
    assert first.chunks[0].startswith(
        "The way the work week works is the worst. Waking up on monday, you've got."
    )
    assert first.duration_ms == 41166
    assert first.voice == Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0)

    assert last.time_ms == 114946
    assert last.chunks[0].endswith("[soft brooding electronic music fades slowly]")
    assert first.duration_ms == 41166
    assert first.voice == Voice(character="Ada Lovelace", pitch=0.0, speech_rate=1.0)

    assert result.audio
    assert result.audio.startswith("https://")
    assert result.audio.endswith(".wav")

    assert result.video
    assert result.video.startswith("https://")
    assert result.video.endswith(".mp4")


@pytest.mark.asyncio
async def test_load_transcribe(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    methods: Sequence[Method] = ("Machine A", "Machine B")

    responses = [
        await transcript.load(
            source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
            method=method,
            lang="en-US",
            session=session,
        )
        for method in methods
    ]

    result_a, result_b = await asyncio.gather(
        *[tasks.future(response) for response in responses]
    )

    # Check Machine A output
    event, *_ = result_a.events

    chunk, *_ = event.chunks
    assert chunk.startswith(
        "The way the work week works is the worst waking up on Monday."  # noqa: E501
    )
    assert chunk.endswith(
        "having a free day when everyone else is working makes so many things easier."  # noqa: E501
    )

    assert result_a.audio.startswith("https://")
    assert result_a.audio.endswith(".wav")

    assert result_a.video.startswith("https://")
    assert result_a.video.endswith(".mp4")

    # Check Machine B output
    event, *_ = result_b.events

    assert event.time_ms == 140
    assert event.duration_ms == pytest.approx(145824, rel=500)

    chunk, *_ = event.chunks

    assert chunk.startswith("The way the work week works is the worst.")
    assert chunk.endswith(
        "If those sound intriguing, why not give it a try and see if weekend Wednesday works for you."  # noqa: E501
    )

    assert result_b.audio.startswith("https://")
    assert result_b.audio.endswith(".wav")

    assert result_b.video.startswith("https://")
    assert result_b.video.endswith(".mp4")
