from typing import Generic, List, Literal, NoReturn, Sequence, TypeGuard, TypeVar

from pydantic.dataclasses import dataclass

url = str
AudioEncoding = Literal["WEBM_OPUS", "LINEAR16", "AAC", "MP3"]
VideoEncoding = Literal["H264", "HEVC", "AV1", "VP9"]
ServiceProvider = Literal["Google", "Deepgram", "Azure", "ElevenLabs"]
TranscriptionModel = Literal["default", "latest_long", "general", "default_granular"]

SpeechToTextBackend = Literal[
    "Machine A", "Machine B", "Machine C", "Machine D", "Subtitles"
]
SPEECH_BACKENDS = ["Machine A", "Machine B", "Machine C", "Machine D", "Subtitles"]


def is_speech_to_text_backend(val: str) -> TypeGuard[SpeechToTextBackend]:
    return val in SPEECH_BACKENDS


TranscriptPlatform = Literal["Google", "Notion"]
TRANSCRIPT_PLATFORMS = ["Google", "Notion"]


def is_transcript_platform(val: str) -> TypeGuard[TranscriptPlatform]:
    return val in TRANSCRIPT_PLATFORMS


MediaPlatform = Literal["YouTube", "GCS", "Twitter"]
MEDIA_PLATFORMS = ["YouTube", "GCS", "Twitter"]


def is_media_platform(val: str) -> TypeGuard[MediaPlatform]:
    return val in MEDIA_PLATFORMS


def platform(url: str) -> TranscriptPlatform | MediaPlatform:
    if not url or not url.startswith(("https://", "gs://")):
        raise ValueError("Invalid URL")

    if url.startswith("https://docs.google.com/document/d/"):
        return "Google"
    elif url.startswith("gs://"):
        return "GCS"
    elif url.startswith("https://www.notion.so/"):
        return "Notion"
    elif (
        url.startswith("https://youtu.be/")
        or url.startswith("https://www.youtube.com/")
        or url.startswith("https://youtube.com/")
    ):
        return "YouTube"
    elif url.startswith("https://twitter.com"):
        return "Twitter"
    else:
        raise ValueError(
            f"Unsupported url: {url}. Supported platforms are: {', '.join(TRANSCRIPT_PLATFORMS + MEDIA_PLATFORMS)}"  # noqa: E501
        )


TranscriptFormat = Literal["SRT", "SSMD", "SSMD-NEXT"]
TRANSCRIPT_FORMATS = ["SRT", "SSMD", "SSMD-NEXT"]


def is_transcript_format(val: str) -> TypeGuard[TranscriptFormat]:
    return val in TRANSCRIPT_FORMATS


Language = Literal[
    "en-US",
    "uk-UA",
    "ru-RU",
    "pt-PT",
    "pt-BR",
    "es-US",
    "es-MX",
    "es-ES",
    "de-DE",
    "fr-FR",
    "sv-SE",
    "tr-TR",
    "it-IT",
    "ar-SA",
    "et-EE",
    "fi-FI",
]
LANGUAGES = [
    "en-US",
    "uk-UA",
    "ru-RU",
    "pt-PT",
    "pt-BR",
    "es-US",
    "es-MX",
    "es-ES",
    "de-DE",
    "fr-FR",
    "sv-SE",
    "tr-TR",
    "it-IT",
    "ar-SA",
    "et-EE",
    "fi-FI",
]

Operation = Literal["Transcribe", "Translate", "Synthesize"]
OPERATIONS = ["Transcribe", "Translate", "Synthesize"]

Character = Literal[
    "Alan",  # Alan Turing
    "Grace",  # Grace Hopper
    "Ada",  # Ada Lovelace
    "Alonzo",  # Alonzo Church
    "Bill",  # Bill Gates
    "Melinda",  # Melinda Gates
    "Greta",  # Greta Thunberg
    "Volodymyr",  # Volodymyr Zelenskyy
]
CHARACTERS: List[Character] = [
    "Alan",
    "Grace",
    "Ada",
    "Alonzo",
    "Bill",
    "Melinda",
    "Greta",
    "Volodymyr",
]

Method = Literal[SpeechToTextBackend, TranscriptFormat]
METHODS = SPEECH_BACKENDS + TRANSCRIPT_FORMATS

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
    """Voice settings for speech synthesis.

    Attributes:
        character (str): Who's voice to use? (Default: `"Ada Lovelace"`)

            - Female characters: `"Ada"`, `"Grace"`, `"Melinda"`, `"Greta"`.
            - Male characters: `"Alonzo"`, `"Alan"`, `"Bill"`.

        pitch (float): Voice pitch. (Default: `0.0`)

            Examples:

            - `0.0` is neutral.
            - `2.0` is higher pitch.
            - `-2.0` is lower pitch.

        speech_rate (float): Speaking rate. (Default: `1.0`)

            Examples:

            - `1.0` is normal rate.
            - `2.0` is 2x faster.
            - `0.5` is 2x slower.
    """

    character: Character = "Ada"
    pitch: float = 0.0
    speech_rate: float = 1.0


@dataclass(frozen=True)
class Event:
    """A timed speech event.

    Contains timed text chunks and information required for speech synthesis:
    pitch, speed, duration.

    Attributes:
        time_ms (int): Time of the event in milliseconds.
        chunks (List[str]): Portions of text (parts, paragraphs).

            Following special tokens are supported:

            - `#1.0#` — speech break for 1 sec.

        duration_ms (int, optional): Event duration.
        voice (Voice): Voice settings.
    """

    time_ms: int
    chunks: List[str]
    duration_ms: int | None = None
    group: int = 0
    voice: Voice = Voice()
    comment: str | None = None


@dataclass(frozen=True)
class Source:
    """Transcript source information.

    Attributes:
        url (str): Public url for the source.
        method (str): How to extract the Transcript from url.

            Machine-based transcription:

            - `"Machine A"`.
            - `"Machine B"`.
            - `"Machine C"`.

            Subtitles:

            - `"Subtitles"` — extract from the video container.
            - `"SRT"` — popular subtitle format.
            - `"SSMD"` — freespeech's speech synthesis markdown.

            Document platforms:

            - `"Google"` — Google Docs.
            - `"Notion"` — Notion.
    """

    method: Method
    url: str | None


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
    original_audio_level: int = 1
    space_between_events: BlankFillMethod = "Fill"


@dataclass(frozen=True)
class Transcript:
    """Information about the transcript.

    Contains information necessary for synthesis, dubbing, and translation.

    Attributes:
        events (Sequence[Event]): A sequence of timed speech events.
            Contains timed text chunks and information required for speech synthesis:
            pitch, speed, duration.
        lang (str): A BCP 47 tag indicating language of a transcript.

            Supported values:

            - `"en-US"` (English).
            - `"uk-UA"` (Ukrainian).
            - `"ru-RU"` (Russian).
            - `"pt-PT"` (Portuguese).
            - `"es-US"` (Spanish).
            - `"de-DE"` (German).

        title (str, optional): Transcript title. Meta-information for transcript
            formats that require a title, such as Google Docs, or Notion.
        source (Source, optional): Transcript source. Contains a `url` and a `method`
            to produce transcript.

            Example:
                ```json
                {
                    "url": "https://www.youtube.com/watch?v=qbYu4OPoKJM",
                    "method": "Subtitles"
                }
                ```
        video (str, optional): Public url for video track for the transcript.
        audio (str, optional): Public url for audio track for the transcript.
        settings (Settings): Settings that specify the behavior of speech
            synthesis and dubbing.
    """

    events: Sequence[Event]
    lang: Language
    title: str | None = None
    source: Source | None = None
    video: str | None = None
    audio: str | None = None
    settings: Settings = Settings()


@dataclass(frozen=True)
class Meta:
    title: str
    duration_ms: int
    description: str
    tags: List[str]


def assert_never(x: NoReturn) -> NoReturn:
    # runtime error, should not happen
    raise Exception(f"Unhandled value: {x}")
