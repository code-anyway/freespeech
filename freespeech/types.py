import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Sequence, Tuple

AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC"]


Language = Literal["en-US", "uk-UK", "ru-RU", "pt-PT", "es-MX"]
Character = Literal["Alan Turing", "Grace Hopper", "Original"]


url = str
_last_updated = datetime.now(tz=timezone.utc).isoformat


@dataclass(frozen=True)
class Voice:
    character: Character
    pitch: float | None = None
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
