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
    speech_rate = None

    match qualifier:
        case "/":
            finish_ms = _to_milliseconds(value)
            duration_ms = finish_ms - start_ms
        case "#":
            duration_ms = round(float(value) * 1000)
        case "@":
            duration_ms = None
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

    def _ms_to_iso_time(ms: int) -> str:
        t = datetime.fromtimestamp(ms / 1000.0, tz=pytz.UTC).time()
        return t.isoformat()

    start_ms = time_ms
    res = f"{_ms_to_iso_time(start_ms)}"

    if duration_ms is None:
        res += f"@{str(voice.speech_rate)}"  # should I round here?
    else:
        finish_ms = time_ms + duration_ms
        res += f"/{_ms_to_iso_time(finish_ms)}"

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
