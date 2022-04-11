import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Tuple

AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC"]

Language = str
Voice = str


url = str
path = Path | str


@dataclass(frozen=True)
class Event:
    time_ms: int
    duration_ms: int
    chunks: List[str]


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


AudioLocator = Tuple[url, Audio]
VideoLocator = Tuple[url, Video]


@dataclass(frozen=True)
class Info:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=False)
class Media:
    audio: List[Tuple[Voice, AudioLocator]] | None
    video: VideoLocator | None
    transcript: List[Event] | None
    lang: Language
    info: Info
    origin: url


@dataclass(frozen=False)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
