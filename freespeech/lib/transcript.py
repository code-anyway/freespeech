import logging
import re
from dataclasses import replace
from datetime import datetime
from typing import Dict, Sequence, Tuple

import pytz

from freespeech.lib import ssmd
from freespeech.typing import (
    BLANK_FILL_METHODS,
    LANGUAGES,
    METHODS,
    TRANSCRIPT_FORMATS,
    Character,
    Event,
    Settings,
    Source,
    Transcript,
    TranscriptFormat,
    Voice,
    assert_never,
    is_blank_fill_method,
    is_character,
    is_language,
    is_method,
    is_transcript_format,
)

logger = logging.getLogger(__name__)

timecode_parser = re.compile(
    r"^\s*(([\d\:\.]+)\s*([/#@])\s*([\d\:\.]+)(\s+\((.+)\))?\s*)$", flags=re.M
)


def to_milliseconds(s: str) -> int:
    if s.find(".") == -1:
        timestamp, after_dot = (s.replace(" ", ""), "0")
    else:
        timestamp, after_dot = s.replace(" ", "").split(".", 1)

    t = datetime.strptime(timestamp, "%H:%M:%S")
    extra_micros = int(after_dot[:6].ljust(6, "0"))
    return (
        t.hour * 60 * 60 * 1_000
        + t.minute * 60 * 1_000
        + t.second * 1_000
        + t.microsecond // 1_000
        + extra_micros // 1_000
    )


def ms_to_iso_time(ms: int) -> str:
    t = datetime.fromtimestamp(ms / 1000.0, tz=pytz.UTC).time()
    return t.isoformat(timespec="microseconds")


def parse_time_interval(
    interval: str,
) -> Tuple[int, int | None, Character | None, float | None]:
    """Parses HH:MM:SS.fff/HH:MM:SS.fff (Character)
    into (start_ms, duration_ms, Character).

    Args:
        interval: start and finish encoded as
            two ISO 8601 formatted timestamps separated by "/"

    Returns:
        Event start time, optional duration in milliseconds, optional character,
        and optional speech rate.
    """
    match = timecode_parser.search(interval)

    if not match:
        raise ValueError(f"Invalid string: {interval}")

    start = match.group(2)
    qualifier = match.group(3)
    value = match.group(4)
    character_str = match.group(6)

    # Leave only the first name.
    # Early on we were using full names, like Ada Lovelace
    if character_str:
        character_str = character_str.split(" ")[0]

    if is_character(character_str):
        character = character_str
    else:
        character = None

    start_ms = to_milliseconds(start)
    speech_rate = None
    duration_ms = None

    match qualifier:
        case "/":
            finish_ms = to_milliseconds(value)
            duration_ms = finish_ms - start_ms
        case "#":
            duration_ms = round(float(value) * 1000)
        case "@":
            speech_rate = float(value)
        case _:
            pass

    return start_ms, duration_ms, character, speech_rate


def unparse_time_interval(time_ms: int, duration_ms: int | None, voice: Voice) -> str:
    """Generates HH:MM:SS.fff/HH:MM:SS.fff (Character) or HH:MM:SS.fff@rr.rr (Character)
    (if speechrate is set) representation for a time interval and voice.

    Args:
        time_ms: interval start time in milliseconds.
        duration_ms: interval duration in milliseconds.
        voice: voice info.

    Returns:
       Interval start and finish encoded as
       two ISO 8601 formatted timespamps separated by "/" with optional
       voice info added.
    """

    start_ms = time_ms
    res = f"{ms_to_iso_time(start_ms)}"

    if duration_ms is None:
        res += f"@{float(voice.speech_rate):.2f}"  # should I round here?
    else:
        finish_ms = time_ms + duration_ms
        res += f"/{ms_to_iso_time(finish_ms)}"

    if voice:
        res = f"{res} ({voice.character})"

    return res


def parse_events(text: str) -> Sequence[Event]:
    events = []
    lines = [line for line in text.split("\n") if line]

    for line in lines:
        if timecode_parser.fullmatch(line):
            start_ms, duration_ms, character, speech_rate = parse_time_interval(line)

            voice = Voice()
            if character is not None:
                voice = replace(voice, character=character)
            if speech_rate is not None:
                voice = replace(voice, speech_rate=speech_rate)

            events += [
                Event(
                    time_ms=start_ms,
                    chunks=[],
                    voice=voice,
                    duration_ms=duration_ms,
                )
            ]
        else:
            if not events:
                logger.warning(f"Paragraph without timestamp: {line}")
            else:
                events += [replace(event := events.pop(), chunks=event.chunks + [line])]

    return events


def parse_properties(text: str) -> Dict[str, str]:
    return {
        k.lower(): v
        for k, v in re.findall(r"\s*(\w+)\s*:\s*(.*)\s*$", text, flags=re.M)
        if v
    }


def parse_transcript(text: str) -> Transcript:
    parts = text.split("\n\n", maxsplit=1)
    if not len(parts) == 2:
        raise ValueError(
            "Expecting two parts: manifest and body separated by two newlines"
        )

    properties = parse_properties(parts[0])
    body = parts[1]

    format = properties.get("format", "SSMD-NEXT")
    if not is_transcript_format(format):
        raise ValueError(
            f"Invalid transcript format: {format}. Supported values: {TRANSCRIPT_FORMATS}"  # noqa: E501
        )

    match format:
        case "SRT":
            events = srt_to_events(body)
        case "SSMD":
            events = parse_events(text=body)
        case "SSMD-NEXT":
            events = ssmd.parse(body)
        case x:
            assert_never(x)

    lang = properties.get("language", None)
    if not lang:
        raise ValueError(f"'language' is not set. Supported values: {LANGUAGES}")
    if not is_language(lang):
        raise ValueError(
            f"Invalid value for 'language': {lang}. Supported values: {LANGUAGES}"
        )

    method = properties.get("method", None)
    if method and not is_method(method):
        raise ValueError(
            f"Invalid value for 'method': {method}. Supported values: {METHODS}"
        )

    origin = properties.get("origin", None)
    if origin and not method:
        raise ValueError(f"'method' is not set. Supported values: {METHODS}")

    if method and is_method(method) and origin:
        source = Source(method=method, url=origin)
    else:
        source = None

    settings = Settings()
    blanks = properties.get("blanks", None)
    if blanks is not None:
        if not is_blank_fill_method(blanks):
            raise ValueError(
                f"Invalid value for 'blanks'. Supported Values: {BLANK_FILL_METHODS}"
            )
        settings = replace(settings, space_between_events=blanks)

    original_audio_level = properties.get("original_audio_level", None)
    if original_audio_level is not None:
        if not str(original_audio_level).isnumeric():
            raise ValueError(
                "Invalid value for 'original_audio_level'. Expected numeric: 1, 2, 3, etc."  # noqa: E501
            )
        settings = replace(settings, original_audio_level=int(original_audio_level))

    video = properties.get("video", None)
    audio = properties.get("audio", None)

    return Transcript(
        title=None,
        lang=lang,
        events=events,
        source=source,
        video=video,
        audio=audio,
        settings=settings,
    )


def render_properties(transcript: Transcript) -> str:
    properties = {
        "language": transcript.lang,
        "method": transcript.source and transcript.source.method,
        "origin": transcript.source and transcript.source.url,
        "audio": transcript.audio,
        "video": transcript.video,
        "original_audio_level": transcript.settings.original_audio_level,
        "blanks": transcript.settings.space_between_events,
    }

    return "\n".join(f"{key}: {value}" for key, value in properties.items() if value)


def render_events(events: Sequence[Event]) -> str:
    output = ""
    for event in events:
        output += "\n"
        output += (
            unparse_time_interval(
                event.time_ms,
                event.duration_ms,
                event.voice,
            )
            + "\n"
        )
        output += "\n".join(event.chunks) + "\n"

    return output


def render_transcript(
    transcript: Transcript,
    format: TranscriptFormat,
) -> str:
    return f"""{render_properties(transcript)}
format: {format}

{render_events(transcript.events)}"""


def srt_to_events(text: str) -> Sequence[Event]:
    """Generates sequence of Events from subtitles stored in .srt format.

    Args:
        text: content of .srt file.

    Returns:
        Speech events parsed from .srt.
    """
    if not text.endswith("\n"):
        text += "\n"
    parser = re.compile(r"\d+\n([\d\:\,]+)\s*-->\s*([\d\:\,]+)\n((.+\n)+)")
    match = parser.findall(text)

    result = [
        Event(
            time_ms=(start_ms := to_milliseconds(start.replace(",", "."))),
            duration_ms=(to_milliseconds(finish.replace(",", ".")) - start_ms),
            chunks=text.split("\n")[:-1],  # there is an extra newline in .srt format
        )
        for start, finish, text, _ in match
    ]

    return result


def remove_special_characters(line: str) -> str:
    """Removes special characters from line."""

    return line.replace("&nbsp;", " ").replace("&amp;", "&")


def vtt_to_events(text: str) -> Sequence[Event]:
    """Generates sequence of Events from subtitles stored in .vtt format.

    Args:
        text: content of .vtt file.

    Returns:
        Speech events parsed from .vtt.
    """
    if not text.endswith("\n"):
        text += "\n"
    parser = re.compile(r"([\d\:\.]+)\s*-->\s*([\d\:\.]+)\n((.+\n)+)")
    match = parser.findall(text)
    result = [
        Event(
            time_ms=(start_ms := to_milliseconds(start)),
            duration_ms=None
            if finish.startswith("99:59:59")  # This magic value means "until the end"
            else (to_milliseconds(finish) - start_ms),
            chunks=[
                " ".join(
                    [remove_special_characters(line) for line in text.split("\n")[:-1]]
                )  # there is an extra newline in .vtt format # noqa: E501
            ],
        )
        for start, finish, text, _ in match
        if not start.startswith("99:59:59")  # We encountered something: like 99:59:59.999 --> 100:00:00.999
    ]

    return result


def events_to_srt(events: Sequence[Event]) -> str:
    text = ""
    for i, e in enumerate(events):
        start = ms_to_iso_time(e.time_ms)
        start = start.replace(".", ",")[:-3]
        finish = ms_to_iso_time(e.time_ms + (e.duration_ms or 0))
        finish = finish.replace(".", ",")[:-3]
        body = "\n".join(e.chunks)
        text += f"{i + 1}\n{start} --> {finish}\n{body}\n\n"

    return text
