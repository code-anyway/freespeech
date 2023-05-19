import itertools
import re
from dataclasses import replace
from functools import reduce
from typing import Sequence

from freespeech.lib import transcript
from freespeech.types import Event, Voice, is_character

TIMECODE_PATTERN = r"(\d{2}:)?\d{2}:\d{2}(\.\d{1,3})?(#(\d+(\.\d+)))?"


# Maximum gap between two adjacent events
MAXIMUM_GAP_MS = 1400


def parse_body(transcript_text: str) -> list[dict[str, str | bool | None]]:
    transcript_text = transcript_text.replace(
        "\u2028", " "
    )  # Replace line separator with space
    lines = transcript_text.splitlines()

    transcript: list[dict] = []

    # Parse transcript
    speaker_regex = r"\(([A-Za-z]+(@(\d+(\.\d+)?))?)\)"

    i = 0
    while i < len(lines):
        comment_lines = []
        text_lines = []

        # Parsing comment
        if "[" in lines[i]:
            while "]" not in lines[i]:
                comment_lines.append(lines[i])
                i += 1

            if lines[i].count("]") > 1:
                raise ValueError("Invalid transcript format.")
            comment_lines.append(lines[i])
            comment = "\n".join([line.strip("[]") for line in comment_lines])
            i += 1
        else:
            comment = None

        if i >= len(lines):
            break

        # Parsing time, speaker, and text
        time_match = re.match(TIMECODE_PATTERN, lines[i])
        if time_match:
            time = time_match.group()
            line = lines[i][len(time) :].strip()
        else:
            time = None
            line = lines[i]

        speaker_match = re.match(speaker_regex, line)
        if speaker_match:
            speaker = speaker_match.group(1)
            line = line[len(speaker) + 2 :].strip()
        else:
            speaker = None

        fixed = (time is not None) and (
            (i > 0 and lines[i - 1].strip() == "") or i == 0
        )

        text_lines.append(line)
        i += 1

        # Multi-line text
        while i < len(lines) and not (
            lines[i].startswith("[")
            or re.match(TIMECODE_PATTERN, lines[i])
            or re.match(speaker_regex, lines[i])
        ):
            text_lines.append(lines[i])
            i += 1

        entry = {
            "time": time,
            "speaker": speaker,
            "text": ("\n".join(text_lines)).strip(),
            "fixed": fixed,
        }

        if comment and (transcript):
            transcript[-1]["comment"] = comment

        if (
            entry.get("text", None)
            or entry.get("comment", None)
            or entry.get("speaker")
            or entry.get("time")
        ):
            transcript.append(entry)

    return transcript


def parse_time(time: str) -> tuple[int, int | None]:
    """Parses timecode string into milliseconds."""

    def parse_timecode(timecode: str) -> int:
        """Parses timecode string into milliseconds."""
        parts = timecode.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            minutes, seconds = parts
            hours = "0"
        else:
            raise ValueError("Invalid timecode format.")

        return int(hours) * 3600000 + int(minutes) * 60000 + int(float(seconds) * 1000)

    if "#" in time:
        time, duration = time.split("#")
        duration_ms = int(float(duration) * 1000)
    else:
        duration_ms = None

    time_ms = parse_timecode(time)

    return time_ms, duration_ms


def make_events(parsed_events: list[dict[str, str | bool | None]]) -> list[Event]:
    """Converts parsed transcript into a sequence of events."""

    events: list[Event] = []
    group = -1
    current_voice = Voice(character="Ada", speech_rate=1.0)

    for parsed_event in parsed_events:
        time = parsed_event["time"]
        text = str(parsed_event["text"])
        speaker = parsed_event["speaker"]

        comment = parsed_event.get("comment", None)
        if not (isinstance(comment, str) or comment is None):
            raise ValueError(f"Invalid comment: {comment}")

        fixed = bool(parsed_event["fixed"])

        # Groups are zero-based
        if fixed or group == -1:
            group += 1

        time_ms = None
        duration_ms = None
        if time and isinstance(time, str):
            time_ms, duration_ms = parse_time(time)

        if speaker and isinstance(speaker, str):
            character_name = speaker.split("@")[0]
            if not is_character(character_name):
                raise ValueError(f"Invalid speaker name: {character_name}")

            voice = Voice(
                character=character_name,
                speech_rate=float(speaker.split("@")[1]) if "@" in speaker else 1.0,
            )
            current_voice = voice
        else:
            voice = current_voice

        if text:
            chunks = [text]
        else:
            chunks = []

        if time_ms is None:
            raise ValueError(f"Missing timecode for {chunks}")
        events.append(
            Event(
                time_ms=time_ms,
                duration_ms=duration_ms,
                chunks=chunks,
                voice=voice,
                comment=comment,
                group=group,
            )
        )

    return events


def parse(s: str) -> Sequence[Event]:
    """Parses SSMD text and extracts speech events turning gaps into blanks."""

    # Parse SSMD
    parsed_events = parse_body(s)

    # Convert parsed SSMD into a sequence of events
    events = make_events(parsed_events)

    return no_gaps(events, threshold_ms=MAXIMUM_GAP_MS)


def no_gaps(events: list[Event], threshold_ms: int) -> list[Event]:
    """Transforms events into a sequence of events with no gaps, adding
    speech pauses and inserting blank events as needed.

    Args:
        events: input event sequence.
        threshold_ms: maximum duration of a pause that will lead to
        creation of a blank event.
    Returns:
        Sequence of events where each event time_ms is equal to the
        previous event time_ms + previous event duration_ms.
    """

    def reducer(acc, event):
        if not acc:
            return [event]

        last = acc.pop()

        if not last.duration_ms:
            last = replace(last, duration_ms=event.time_ms - last.time_ms)

        interval_ms = event.time_ms - last.time_ms
        gap_ms = interval_ms - last.duration_ms

        if gap_ms < threshold_ms:
            last = replace(
                last,
                duration_ms=interval_ms,
                chunks=[
                    " ".join(last.chunks)
                    + ("" if gap_ms < 50 else f" #{gap_ms / 1000:.1f}#")
                ],
            )
            return acc + [last, event]
        else:
            silence = Event(
                time_ms=event.time_ms - gap_ms,
                duration_ms=gap_ms,
                chunks=[""],
                group=last.group,
                voice=last.voice,
            )
            return acc + [last, silence, event]

    return reduce(reducer, events, [])


def render_block(events: Sequence[Event]) -> str:
    lines: list[str] = []
    previous_voice = None

    for event, next_event in zip(events, list(events[1:]) + [events[-1]]):
        time = (
            transcript.ms_to_iso_time(event.time_ms)[:-4]
            if event.time_ms is not None
            else ""
        )
        if time:
            # Remove hours if less than 1 hour
            if event.time_ms < 3600_000:
                time = time[3:]

        event_text = "\n".join(event.chunks)
        if event.duration_ms is not None:
            if next_event == event or (
                next_event.time_ms - event.time_ms != event.duration_ms
            ):
                time += f"#{event.duration_ms/1000.0:.2f}"

        if event.voice.speech_rate != 1.0:
            voice = f"{event.voice.character}@{event.voice.speech_rate:.1f}"
        else:
            voice = event.voice.character

        if event.comment:
            comment = f"\n[{event.comment}]"
        else:
            comment = ""

        if event.voice != previous_voice:
            lines += [f"{time} ({voice}) {event_text}{comment}".strip()]
            previous_voice = event.voice
        else:
            lines += [f"{time} {event_text}{comment}".strip()]
    return "\n".join(lines)


def render(events: list[Event]) -> str:
    """Renders a sequence of events into a sequence with no gaps in SSMD format.

    Args:
        events: events to be rendered.
    Returns:
        String in SSMD format, with events grouped by event.group
        and separated by empty lines.
    """
    events = no_gaps(events, threshold_ms=MAXIMUM_GAP_MS)
    blocks = [
        render_block(list(block))
        for _, block in itertools.groupby(events, lambda event: event.group)
    ]
    return "\n\n".join(blocks)
