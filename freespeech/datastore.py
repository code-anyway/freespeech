from google.cloud import firestore
from freespeech.types import Media, Audio, Video, Stream, Transcript, Event
from freespeech import env
from dataclasses import asdict
from typing import Literal, List


COLLECTIONS = {
    Media: "media",
    Audio: "audio",
    Video: "video",
    Transcript: "transcript"
}

EntityKind = Literal["media", "audio", "video", "transcript"]


def _client():
    project_id = env.get_project_id()
    client = firestore.Client(project=project_id)
    return client


def put(value: Media | Audio | Video | Stream | Transcript):
    client = _client()

    if isinstance(value, Media):
        for audio in value.audio:
            put(audio)

        for video in value.video:
            put(video)

    doc = client.collection(COLLECTIONS[type(value)]).document(value._id)

    if isinstance(value, Media):
        doc.set({
            **asdict(value),
            "audio": [audio._id for audio in value.audio],
            "video": [video._id for video in value.video]
        })
    else:
        doc.set(asdict(value))


def get(_id: str, kind: EntityKind):
    client = _client()

    doc = client.collection(kind).document(_id)
    value = doc.get().to_dict()

    match kind:
        case "media":
            audio = [get(entity, "audio") for entity in value["audio"]]
            video = [get(entity, "video") for entity in value["video"]]
            return Media(
                _id=_id,
                video=video,
                audio=audio,
                title=value["title"],
                description=value["description"],
                tags=value["tags"],
                origin=value["origin"]
            )
        case "audio":
            return Audio(
                duration_ms=value["duration_ms"],
                storage_url=env.get_storage_url(),
                suffix=value["suffix"],
                url=value["url"],
                _id=_id,
                encoding=value["encoding"],
                sample_rate_hz=value["sample_rate_hz"],
                voice=value["voice"],
                lang=value["lang"],
                num_channels=value["num_channels"]
            )
        case "video":
            return Video(
                duration_ms=value["duration_ms"],
                storage_url=env.get_storage_url(),
                suffix=value["suffix"],
                url=value["url"],
                _id=_id,
                encoding=value["encoding"],
                fps=value["fps"]
            )
        case "transcript":
            return Transcript(
                lang=value["lang"],
                _id=value["_id"],
                events=[
                    Event(
                        time_ms=event["time_ms"],
                        duration_ms=event["duration_ms"],
                        chunks=event["chunks"]
                    )
                    for event in value["events"]
                ]
            )
        case unknown_type:
            raise ValueError(f"Unknown entity type: {unknown_type}")


def get_by_key_value(key: str, value: str, kind: EntityKind) -> List[Media]:
    client = _client()

    query = client.collection(kind).where(key, "==", value)
    res = query.stream()

    return [
        get(_id=item.to_dict()["_id"], kind=kind)
        for item in res
    ]
