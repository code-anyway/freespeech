import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple


AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264"]

# For URLs/URIs.
Locator = str
Language = str
Voice = str


@dataclass(frozen=True)
class Event:
    time_ms: int
    duration_ms: int
    chunks: List[str]


@dataclass(frozen=True)
class Stream:
    duration_ms: int
    ext: str


@dataclass(frozen=True)
class Audio(Stream):
    encoding: AudioEncoding
    sample_rate_hz: int
    num_channels: int = 1


@dataclass(frozen=True)
class Video(Stream):
    encoding: VideoEncoding
    # TODO (astaff): add fps, HxW, etc


AudioLocator = Tuple[Locator, Audio]
VideoLocator = Tuple[Locator, Video]


@dataclass(frozen=True)
class Info:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=False)
class Media:
    audio: List[Tuple[Voice, AudioLocator]]
    video: VideoLocator
    transcript: List[Event]
    lang: Language
    info: Info
    origin: Locator


@dataclass(frozen=False)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
