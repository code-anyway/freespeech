from typing import List, Literal
from dataclasses import dataclass


Locator = str
Language = Literal["en-US", "uk-UK", "ru-RU"]
Voice = Literal["us-W"]


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
    i
    duration_ms: float | None
    title: str
    description: str
    url: str
    source: str
    transcript: Transcript | None


Audio = Media
Video = Media


    
    
    



def synthesize(t: Transcript) -> Audio:
    pass


def voiceover(v: Video, a: Audio) -> Video:
    pass


def mix(streams: List[Audio], weights: List[int]) -> Audio:
    pass


def download(v: Locator) -> Video:
    pass


def translate(t: Transcript) -> Transcript:
    pass


Asset = Audio | Video
