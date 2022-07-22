from typing import Dict, Generic, List, Literal, NoReturn, Sequence, TypeGuard, TypeVar

from pydantic.dataclasses import dataclass

url = str
AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC"]
VideoEncoding = Literal["H264", "HEVC", "AV1"]
ServiceProvider = Literal["Google", "Deepgram", "Azure"]
TranscriptionModel = Literal["default", "latest_long", "general"]

SpeechToTextBackend = Literal["C3PO", "R2D2", "BB8"]
SPEECH_BACKENDS = ["C3PO", "R2D2", "BB8"]

TranscriptBackend = Literal["Google", "Notion", "SRT", "SSMD"]
TRANSCRIPT_BACKENDS = ["Google", "Notion", "SRT", "SSMD"]

Language = Literal["en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE"]
LANGUAGES = ["en-US", "uk-UA", "ru-RU", "pt-PT", "es-US", "de-DE"]

Operation = Literal["Transcribe", "Translate", "Synthesize"]
OPERATIONS = ["Transcribe", "Translate", "Synthesize"]

Character = Literal[
    "Alan Turing",
    "Grace Hopper",
    "Ada Lovelace",
    "Alonzo Church",
    "Bill",
    "Melinda",
]
CHARACTERS = [
    "Alan Turing",
    "Grace Hopper",
    "Ada Lovelace",
    "Alonzo Church",
    "Bill",
    "Melinda",
]

Method = Literal[SpeechToTextBackend, TranscriptBackend, "Subtitles"]
METHODS = SPEECH_BACKENDS + TRANSCRIPT_BACKENDS + ["Subtitles"]

BlankFillMethod = Literal["Crop", "Blank", "Fill"]
BLANK_FILL_METHODS = ["Crop", "Blank", "Fill"]


def is_language(val: str) -> TypeGuard[Language]:
    return val in LANGUAGES


def is_operation(val: str) -> TypeGuard[Operation]:
    return val in OPERATIONS


def is_character(val: str) -> TypeGuard[Character]:
    return val in CHARACTERS


def is_method(val: str) -> TypeGuard[Method]:
    return val in METHODS


def is_blank_fill_method(val: str) -> TypeGuard[BlankFillMethod]:
    return val in BLANK_FILL_METHODS


@dataclass(frozen=True)
class Voice:
    character: Character = "Ada Lovelace"
    pitch: float = 0.0
    speech_rate: float = 1.0


@dataclass(frozen=True)
class Event:
    time_ms: int
    chunks: List[str]
    duration_ms: int | None = None
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


MediaType = TypeVar("MediaType", Audio, Video)


@dataclass(frozen=True)
class Media(Generic[MediaType]):
    url: str
    info: MediaType | None


@dataclass(frozen=True)
class Settings:
    original_audio_level: int = 2
    space_between_events: BlankFillMethod = "Blank"


@dataclass(frozen=True)
class Transcript:
    lang: Language
    events: Sequence[Event]
    title: str | None = None
    source: Source | None = None
    video: Media[Video] | None = None
    audio: Media[Audio] | None = None
    settings: Settings = Settings()


@dataclass(frozen=True)
class Meta:
    title: str
    description: str
    tags: List[str]


@dataclass(frozen=True)
class Error:
    message: str
    details: str | None = None


@dataclass(frozen=True)
class SynthesizeRequest:
    transcript: Transcript


@dataclass(frozen=True)
class TranslateRequest:
    transcript: Transcript
    lang: Language


@dataclass(frozen=True)
class LoadRequest:
    source: str | None
    method: Method
    lang: Language | None


@dataclass(frozen=True)
class IngestRequest:
    source: str | None


@dataclass(frozen=True)
class IngestResponse:
    audio: str | None
    video: str | None


@dataclass(frozen=True)
class AskRequest:
    message: str
    intent: Operation | None
    state: Dict


@dataclass(frozen=True)
class AskResponse:
    message: str
    state: Dict


def assert_never(x: NoReturn) -> NoReturn:
    # runtime error, should not happen
    raise Exception(f"Unhandled value: {x}")
