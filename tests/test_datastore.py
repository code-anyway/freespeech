import pytest
import uuid


from freespeech import env
from freespeech.lib.storage import document
from freespeech.types import Audio, Video, Media, Transcript, Event


@pytest.mark.asyncio
async def test_all(monkeypatch):
    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "https://freespeech-tests/")

    audio = [
        Audio(
            duration_ms=42 * i,
            storage_url=env.get_storage_url(),
            suffix="wav",
            encoding="WEBM_OPUS",
            sample_rate_hz=16_000 * i,
            voice="ru-RU-Wavenet-D",
            lang="ru-RU",
            num_channels=i
        )
        for i in range(3)
    ]
    video = [
        Video(
            duration_ms=42 * i,
            storage_url=env.get_storage_url(),
            suffix="wav",
            encoding="H264",
            fps=25 * i,
        )
        for i in range(3)
    ]

    origin_value = f"https://youtube.com/{uuid.uuid4()}"
    media = Media(
        audio=audio,
        video=video,
        title="ABC",
        description="123",
        tags=["foo", "bar"],
        origin=origin_value
    )

    document.put(media)

    res = document.get(media._id, kind="media")

    assert res == media

    res = document.get_by_key_value(
        "origin",
        origin_value,
        "media")

    assert res == [media]


def test_transcript():
    transcript = Transcript(
        lang="en-US",
        events=[
            Event(
                time_ms=10,
                duration_ms=100,
                chunks=["123", "abc"]
            ),
            Event(
                time_ms=400,
                duration_ms=100,
                chunks=["foo"]
            )
        ]
    )

    document.put(transcript)

    res = document.get(transcript._id, "transcript")

    assert res == transcript
