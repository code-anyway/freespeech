import uuid
from dataclasses import dataclass, field
from typing import List, Literal, NoReturn, Sequence, TypeGuard

url = str
AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC", "AV1"]
ServiceProvider = Literal["Google", "Deepgram", "Azure"]
TranscriptionModel = Literal["default", "latest_long", "general"]
SpeechToText = Literal["C3PO", "R2D2", "BB8"]
DocumentFormat = Literal["Google", "Notion", "SRT"]
Language = Literal["en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE"]


def is_language(val: str) -> TypeGuard[Language]:
    return val in ("en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE")


Character = Literal[
    "Alan Turing",
    "Grace Hopper",
    "Ada Lovelace",
    "Alonzo Church",
    "Bill",
    "Melinda",
]


def is_character(val: str) -> TypeGuard[Character]:
    return val in (
        "Bill",
        "Melinda",
        "Alan Turing",
        "Grace Hopper",
        "Ada Lovelace",
        "Alonzo Church",
        "Original",
    )


Method = Literal[SpeechToText, "Subtitles", "Translate"]


def is_method(val: str) -> TypeGuard[Method]:
    return val in ("C3PO", "R2D2", "BB8", "Subtitles", "Translate")


@dataclass(frozen=True)
class Voice:
    character: Character = "Alan Turing"
    pitch: float = 0.0
    speech_rate: float = 1.0


@dataclass(frozen=True)
class Event:
    time_ms: int
    duration_ms: int | None
    chunks: List[str]
    voice: Voice = Voice()


@dataclass(frozen=True)
class Source:
    method: Method
    url: str


@dataclass(frozen=True)
class Audio:
    url: str
    duration_ms: int
    encoding: AudioEncoding
    sample_rate_hz: int
    num_channels: int


@dataclass(frozen=True)
class Video:
    url: str
    duration_ms: int
    encoding: VideoEncoding
    # TODO (astaff): add fps, HxW, etc


@dataclass(frozen=True)
class Settings:
    original_audio_level: int = 2
    gaps: Literal["Crop", "Blank", "Fill"] = "Blank"


@dataclass(frozen=True)
class Transcript:
    title: str | None
    lang: Language
    events: Sequence[Event]
    origin: Source | None
    audio_url: str | None
    video_url: str | None
    settings: Settings


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=True)
class Job:
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]
    _id: uuid.UUID = field(default_factory=uuid.uuid4)


def assert_never(x: NoReturn) -> NoReturn:
    # runtime error, should not happen
    raise Exception(f"Unhandled value: {x}")
