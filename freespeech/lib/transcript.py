import logging
import re
from dataclasses import replace
from datetime import datetime
from typing import Sequence, Tuple

from freespeech.types import Character, Event, Voice, is_character

logger = logging.getLogger(__name__)

timecode_parser = re.compile(r"(([\d\:\.]+)\s*([/#@])\s*([\d\:\.]+)(\s+\((.+)\))?)")


def parse_time_interval(interval: str) -> Tuple[int, int, Character | None]:
    """Parses HH:MM:SS.fff/HH:MM:SS.fff (Character) into (start_ms, duration_ms, Character).

    Args:
        interval: start and finish encoded as
            two ISO 8601 formatted timestamps separated by "/"

    Returns:
        Event start time and duration in milliseconds and optional character.
    """

    # TODO (astaff): couldn't find a sane way to do that
    # other than parsing it as datetime from a custom
    # ISO format that ingores date. Hence this.
    def _to_milliseconds(s: str):
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

    start_ms = _to_milliseconds(start)
    if qualifier == "/":
        finish_ms = _to_milliseconds(value)
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
        t = datetime.fromtimestamp(ms / 1000.0).time()
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
