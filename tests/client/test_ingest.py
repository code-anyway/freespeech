import pytest

from freespeech.client import client, media, tasks
from freespeech.types import Error


@pytest.mark.skip(reason="Long test, enable to call ingest")
@pytest.mark.asyncio
async def test_ingest_jsononly_longvideo(client):
    import time

    start_time = time.time()

    # resp = await media_client.ingest(
    #     "https://www.youtube.com/watch?v=Gm4qV0wX8f0", session=client
    # )
    print("--- %s seconds ---" % (time.time() - start_time))


@pytest.mark.asyncio
async def test_ingest_local_stream(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        with open("tests/lib/data/media/dub-en-US-ru-RU.mp4", "rb") as file:
            response = await media.ingest(
                file, filename="dub-en-US-ru-RU.mp4", session=session
            )

            result = await tasks.future(response)
            if isinstance(result, Error):
                assert False, result.message

            assert result.audio
            assert result.audio.startswith("https://")
            # we are using the same stream as audio and video
            assert result.audio.endswith(".mp4")

            assert result.video
            assert result.video.startswith("https://")
            assert result.video.endswith(".mp4")


@pytest.mark.asyncio
async def test_ingest_youtube_short(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    # session = client.create()

    async with session:
        response = await media.ingest(
            "https://www.youtube.com/watch?v=hgV8mB-M9po", session=session
        )
        result = await tasks.future(response)
        if isinstance(result, Error):
            assert False, result.message

        assert result.audio
        assert result.audio.startswith("https://")
        assert result.audio.endswith(".wav")

        assert result.video
        assert result.video.startswith("https://")
        assert result.video.endswith(".mp4")
