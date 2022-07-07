import logging
from pathlib import Path
import re
from dataclasses import replace
from datetime import datetime
from typing import Sequence, Tuple

import pytz

from freespeech.types import Character, Event, Voice, is_character

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


def parse_time_interval(interval: str) -> Tuple[int, int, Character | None]:
    """Parses HH:MM:SS.fff/HH:MM:SS.fff (Character) into (start_ms, duration_ms, Character).

    Args:
        interval: start and finish encoded as
            two ISO 8601 formatted timestamps separated by "/"

    Returns:
        Event start time and duration in milliseconds and optional character.
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
    if qualifier == "/":
        finish_ms = to_milliseconds(value)
        duration_ms = finish_ms - start_ms
    elif qualifier == "#":
        duration_ms = round(float(value) * 1000)

    return start_ms, duration_ms, character


def unparse_time_interval(time_ms: int, duration_ms: int, voice: Voice | None) -> str:
    """Generates HH:MM:SS.fff/HH:MM:SS.fff (Character)?
    representation for a time interval and voice.

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
    finish_ms = time_ms + duration_ms

    def _ms_to_iso_time(ms: int) -> str:
        t = datetime.fromtimestamp(ms / 1000.0, tz=pytz.UTC).time()
        return t.isoformat()

    res = f"{_ms_to_iso_time(start_ms)}/{_ms_to_iso_time(finish_ms)}"

    if voice:
        res = f"{res} ({voice.character})"

    return res


def parse_events(text: str) -> Sequence[Event]:
    events = []
    lines = [line for line in text.split("\n") if line]

    for line in lines:
        if timecode_parser.fullmatch(line):
            start_ms, duration_ms, character = parse_time_interval(line)
            events += [
                Event(
                    start_ms,
                    duration_ms,
                    chunks=[],
                    voice=Voice(character) if character else None,
                )
            ]
        else:
            if not events:
                logger.warning(f"Paragraph without timestamp: {line}")
            else:
                events += [replace(event := events.pop(), chunks=event.chunks + [line])]

    return events


def parse_srt(srt_file: Path | str) -> Sequence[Event]:
    """Generates sequence of Events out of .srt file.

    Args:
        srt_file: path to an .srt file.

    Returns:
        Speeched events parsed from .srt file.
    """
    with open(srt_file, "r") as fd:
        text = "".join(list(fd)) + "\n"

    parser = re.compile(r"\d+\n([\d\:\,]+)\s*-->\s*([\d\:\,]+)\n((.+\n)+)")
    match = parser.findall(text)

    result = [
        Event(
            time_ms=(start_ms := to_milliseconds(start.replace(",", "."))),
            duration_ms=(
                to_milliseconds(finish.replace(",", ".")) - start_ms
            ),
            chunks=[(" ".join(text.split("\n"))).strip()],
        )
        for start, finish, text, _ in match
    ]

    return result

