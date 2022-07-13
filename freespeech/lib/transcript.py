import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Sequence, Tuple

import pytz

from freespeech.types import Character, Event, Language, Source, Voice, is_character

logger = logging.getLogger(__name__)

timecode_parser = re.compile(
    r"^\s*(([\d\:\.]+)\s*([/#@])\s*([\d\:\.]+)(\s+\((.+)\))?\s*)$", flags=re.M
)


@dataclass
class Page:
    origin: str
    language: Language
    voice: Character
    clip_id: str
    method: Source
    original_audio_level: int
    video: str | None


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
    """Parses HH:MM:SS.fff/HH:MM:SS.fff (Character) into (start_ms, duration_ms, Character).

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


def parse_events(text: str, context: Page) -> Sequence[Event]:
    events = []
    lines = [line for line in text.split("\n") if line]

    for line in lines:
        if timecode_parser.fullmatch(line):
            start_ms, duration_ms, character, speech_rate = parse_time_interval(line)
            character = character or context.voice
            # TODO: look below, 1.0 should be a default in context. same for character!
            speech_rate = (
                speech_rate or 1.0
            )  # this feels wrong but that's the entrypoint
            events += [
                Event(
                    start_ms,
                    duration_ms,
                    chunks=[],
                    voice=Voice(character=character, speech_rate=speech_rate),
                )
            ]
        else:
            if not events:
                logger.warning(f"Paragraph without timestamp: {line}")
            else:
                events += [replace(event := events.pop(), chunks=event.chunks + [line])]

    return events


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
