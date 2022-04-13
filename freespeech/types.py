import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Tuple, Sequence


AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC"]


Language = str
Voice = str
SpeechRate = str


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


AudioStream = Tuple[url, Audio]
VideoStream = Tuple[url, Video]


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=False)
class Clip:
    origin: url
    lang: Language
    voice: Voice
    audio: AudioStream
    video: VideoStream | None
    transcript: Sequence[Tuple[Event, SpeechRate]]
    meta: Meta
    last_updated: datetime = datetime.now()


@dataclass(frozen=False)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
