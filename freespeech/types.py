import uuid
from dataclasses import InitVar, dataclass, field
from typing import List, Literal
from urllib.parse import urlparse, urlunparse
from pathlib import Path


Locator = str
Language = Literal["en-US", "uk-UK", "ru-RU"]
Voice = Literal["ru-RU-Wavenet-D", "en-US-Wavenet-I"]
AudioEncoding = Literal["WEBM_OPUS", "LINEAR16"]


@dataclass(frozen=False)
class Event:
    time_ms: int
    duration_ms: int
    chunks: List[str]


@dataclass(frozen=True)
class Transcript:
    lang: Language
    events: List[Event]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=False)
class Stream:
    duration_ms: int
    storage_url: InitVar[str]
    suffix: str
    url: str | None = None
    _id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self, storage_url):
        if self.url is None:
            # handle optional trailing / in storage_url gracefully
            scheme, netloc, path, params, query, fragment = \
                urlparse(storage_url)
            path = str(Path(path) / f"{self._id}.{self.suffix}")
            self.url = \
                urlunparse((scheme, netloc, path, params, query, fragment))


@dataclass(frozen=False)
class Audio(Stream):
    encoding: AudioEncoding | None = None
    sample_rate_hz: int | None = None
    voice: Voice | None = None
    lang: Language | None = None
    num_channels: int = 1


@dataclass(frozen=False)
class Media:
    audio: List[Stream]
    video: List[Stream]
    title: str
    description: str
    tags: List[str]
    origin: str
    _id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=False)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
