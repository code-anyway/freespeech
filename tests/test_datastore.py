import pytest


from freespeech import env, datastore
from freespeech.types import Audio, Video, Media, Transcript, Event


@pytest.mark.asyncio
async def test_all(datastore_emulator, monkeypatch):
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

    media = Media(
        audio=audio,
        video=video,
        title="ABC",
        description="123",
        tags=["foo", "bar"],
        origin="https://youtube.com"
    )

    datastore.put(media)

    res = datastore.get(media._id, kind="media")

    assert res == media

    res = datastore.get_by_key_value(
        "origin",
        "https://youtube.com",
        "media")

    assert res == [media]


def test_transcript(datastore_env, datastore_emulator):
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

    datastore.put(transcript)

    res = datastore.get(transcript._id, "transcript")

    assert res == transcript
