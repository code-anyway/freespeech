import asyncio
from typing import Sequence

import pytest

from freespeech.client import client, tasks, transcript
from freespeech.types import Error, Event, Method, Voice


@pytest.mark.asyncio
async def test_load_srt(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        with open("tests/lib/data/transcript/fmj.srt", "rb") as stream:
            task = await transcript.load(
                source=stream, method="SRT", lang="en-US", session=session
            )
            result = await tasks.future(task, session)
            if isinstance(result, Error):
                assert False, result.message

            first, *_, last = result.events
            assert first == Event(
                time_ms=27110,
                chunks=['"America has heard the bugle call'],
                duration_ms=5050,
                voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            )
            assert last == Event(
                time_ms=6716480,
                chunks=["And I am not afraid."],
                duration_ms=1580,
                voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            )


@pytest.mark.asyncio
async def test_load_srt_from_gdoc(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        task = await transcript.load(
            source="https://docs.google.com"
            "/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY"
            "/edit?usp=sharing",
            method="SRT",
            lang="en-US",
            session=session,
        )
        result = await tasks.future(task, session)
        if isinstance(result, Error):
            assert False, result.message

        first, *_, last = result.events
        print(result.events)
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
async def test_load_ssmd(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        with open("tests/lib/data/transcript/test.ssmd", "rb") as stream:
            task = await transcript.load(
                source=stream, method="SSMD", lang="en-US", session=session
            )
            result = await tasks.future(task, session)
            if isinstance(result, Error):
                assert False, result.message

            first, *_, last = result.events
            assert first == Event(
                time_ms=0,
                chunks=["Hello, Bill!", "How are you?"],
                duration_ms=1000,
                voice=Voice(character="Grace", pitch=0.0, speech_rate=1.0),
            )
            assert last == Event(
                time_ms=2000,
                chunks=["It was a huge mistake."],
                duration_ms=None,
                voice=Voice(character="Ada", pitch=0.0, speech_rate=1.4),
            )


@pytest.mark.asyncio
async def test_load_subtitles(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        task = await transcript.load(
            source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
            method="Subtitles",
            lang="en-US",
            session=session,
        )

        result = await tasks.future(task, session)

    if isinstance(result, Error):
        assert False, result.message

    first, *_, last = result.events

    assert first.time_ms == 0
    assert first.chunks[0].startswith(
        "The way the work week works is the worst. Waking up on monday, you've got."
    )
    assert first.duration_ms == 41166
    assert first.voice == Voice(character="Ada", pitch=0.0, speech_rate=1.0)

    assert last.time_ms == 114946
    assert last.chunks[0].endswith("[soft brooding electronic music fades slowly]")
    assert first.duration_ms == 41166
    assert first.voice == Voice(character="Ada", pitch=0.0, speech_rate=1.0)

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
    # session = client.create()

    async with session:
        methods: Sequence[Method] = ("Machine A", "Machine B", "Machine C")

        responses = [
            await transcript.load(
                source="https://www.youtube.com/watch?v=bhRaND9jiOA",
                method=method,
                lang="en-US",
                session=session,
            )
            for method in methods
        ]

        result_a, result_b, result_c = await asyncio.gather(
            *[tasks.future(response, session) for response in responses]
        )

    # Check Machine A output
    event, *_ = result_a.events
    chunk, *_ = event.chunks

    assert "One" in chunk
    assert "procrastination and sloth" in chunk

    assert result_a.audio.startswith("https://")
    assert result_a.audio.endswith(".wav")

    assert result_a.video.startswith("https://")
    assert result_a.video.endswith(".mp4")

    # Check Machine B output
    event, *_ = result_b.events
    chunk, *_ = event.chunks

    assert "one" in chunk
    assert "procrastination and sloth" in chunk

    assert result_b.audio.startswith("https://")
    assert result_b.audio.endswith(".wav")

    assert result_b.video.startswith("https://")
    assert result_b.video.endswith(".mp4")

    # Check Machine C output
    event, *_ = result_c.events
    chunk, *_ = event.chunks

    assert chunk.startswith("One")
    assert "procrastination and sloth" in chunk

    assert result_c.audio.startswith("https://")
    assert result_c.audio.endswith(".wav")

    assert result_c.video.startswith("https://")
    assert result_c.video.endswith(".mp4")
