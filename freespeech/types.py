import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, NoReturn, Sequence, Tuple, TypeGuard

AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC", "AV1"]
ServiceProvider = Literal["Google", "Deepgram", "Azure"]


Language = Literal["en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE"]
Character = Literal[
    "Alan Turing", "Grace Hopper", "Ada Lovelace", "Alonzo Church", "Original"
]


def is_language(val: str) -> TypeGuard[Language]:
    return val in ("en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE")


def is_character(val: str) -> TypeGuard[Character]:
    return val in (
        "Alan Turing",
        "Grace Hopper",
        "Ada Lovelace",
        "Alonzo Church",
        "Original",
    )


url = str
_last_updated = datetime.now(tz=timezone.utc).isoformat


@dataclass(frozen=True)
class Voice:
    character: Character
    pitch: float = 0.0
    speech_rate: float | None = None


@dataclass(frozen=True)
class Event:
    time_ms: int
    duration_ms: int
    chunks: List[str]
    voice: Voice | None = None


@dataclass(frozen=True)
class Audio:
    duration_ms: int
    encoding: AudioEncoding
    sample_rate_hz: int
    num_channels: int


@dataclass(frozen=True)
class Video:
    duration_ms: int
    encoding: VideoEncoding
    # TODO (astaff): add fps, HxW, etc


AudioStream = Tuple[url, Audio]
VideoStream = Tuple[url, Video]


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=True)
class Clip:
    origin: url
    lang: Language
    audio: AudioStream
    video: VideoStream | None
    transcript: Sequence[Event]
    meta: Meta
    parent_id: str | None
    _id: str = field(default=str(uuid.uuid4()))
    last_updated: str = field(default=_last_updated())


@dataclass(frozen=True)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)


def assert_never(x: NoReturn) -> NoReturn:
    # runtime error, should not happen
    raise Exception(f"Unhandled value: {x}")
