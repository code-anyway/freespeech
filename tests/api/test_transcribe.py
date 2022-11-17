import pytest


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
        "The way the work week works is the worst. Waking up on Monday, you've got"
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

    assert "One" in chunk
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
