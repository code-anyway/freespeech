from pathlib import Path
from dataclasses import dataclass
from typing import List, Literal

Locator = str
Language = Literal["en-US", "uk-UK", "ru-RU"]
Voice = Literal["ru-RU-Wavenet-D", "en-US-Wavenet-I"]


@dataclass(frozen=False)
class Event:
    time_ms: float
    duration_ms: float
    chunks: List[str]


@dataclass(frozen=True)
class Transcript:
    lang: Language
    events: List[Event]


@dataclass(frozen=False)
class Media:
    id: str
    duration_ms: float | None
    title: str
    description: str
    origin: str
    file: str | None
    transcript: Transcript | None
    voice: Voice


Audio = Media
Video = Media


@dataclass(frozen=False)
class Job:
    id: str
    status: Literal["Successful", "Cancelled", "Pending", "Failed"]


@dataclass(frozen=True)
class FileStorage:
    path: Path


@dataclass(frozen=True)
class GoogleStorage:
    bucket: str
    path: str


Storage = FileStorage | GoogleStorage


def synthesize(tr: Transcript, vo: Voice, rate: int) -> Audio:
    """
    Synthesize speech from transcript using voice `vo` and speaking `rate`
    """
    pass


def add_audio(vi: Video, au: Audio) -> Video:
    """Set audio for a video stream"""
    pass


def voiceover(vi: Video, tr: Transcript, vo: Voice) -> Video:
    pass


def mix(au: List[Audio], w: List[int]) -> Audio:
    pass


def download(url: Locator) -> Video:
    pass
