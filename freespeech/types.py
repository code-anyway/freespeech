from typing import Dict, List, Literal, NoReturn, Sequence, Tuple, TypeGuard

from pydantic.dataclasses import dataclass

url = str
AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC", "AV1"]
ServiceProvider = Literal["Google", "Deepgram", "Azure"]
TranscriptionModel = Literal["default", "latest_long", "general"]
SpeechToTextBackend = Literal["C3PO", "R2D2", "BB8"]
TranscriptBackend = Literal["Google", "Notion", "SRT", "SSMD"]
Language = Literal["en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE"]
Operation = Literal["Transcribe", "Translate", "Synthesize"]


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
    )


Method = Literal[SpeechToTextBackend, TranscriptBackend, "Subtitles", "Translate"]


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
    duration_ms: int
    encoding: AudioEncoding
    sample_rate_hz: int
    num_channels: int


@dataclass(frozen=True)
class Video:
    duration_ms: int
    encoding: VideoEncoding


@dataclass(frozen=True)
class Media:
    video: Tuple[str, Video | None] | None
    audio: Tuple[str, Audio | None] | None


@dataclass(frozen=True)
class Settings:
    original_audio_level: int = 2
    gaps: Literal["Crop", "Blank", "Fill"] = "Blank"


@dataclass(frozen=True)
class Transcript:
    title: str | None
    lang: Language
    events: Sequence[Event]
    source: Source | None
    media: Media | None
    settings: Settings


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=True)
class Job:
    op: Operation
    state: Literal["Done", "Cancelled", "Running", "Pending", "Failed"]
    message: str | None
    id: str | None


@dataclass(frozen=True)
class Error:
    state: Dict
    message: str
    details: str | None = None


@dataclass(frozen=True)
class Message:
    text: str
    intent: Operation | None
    state: Dict


@dataclass(frozen=True)
class SynthesizeRequest:
    transcript: Transcript


@dataclass(frozen=True)
class TranslateRequest:
    transcript: Transcript
    lang: Language


@dataclass(frozen=True)
class TranscriptReuqest:
    url: str
    method: Method
    lang: Language


def assert_never(x: NoReturn) -> NoReturn:
    # runtime error, should not happen
    raise Exception(f"Unhandled value: {x}")
