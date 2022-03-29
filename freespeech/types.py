import uuid
from dataclasses import InitVar, dataclass, field
from typing import List, Literal

Locator = str
Language = Literal["en-US", "uk-UK", "ru-RU"]
Voice = Literal["ru-RU-Wavenet-D", "en-US-Wavenet-I"]


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
    url: str = field(init=False)
    storage_url: InitVar[str]
    suffix: InitVar[str]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self, storage_url, suffix):
        self.url = f"{storage_url}/{self._id}.{suffix}"


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
