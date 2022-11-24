import itertools
import re
from dataclasses import replace
from functools import reduce
from typing import Sequence

from freespeech.lib import text, transcript
from freespeech.types import Event, Voice, is_character

TIMECODE_PATTERN = (
    r"(([\d\:\.]+)?\s*(([/#])\s*([\d\:\.]+))?\s*(\((.+?)(@(\d+(\.\d+)?))?\)))"
)
timecode_parser = re.compile(
    rf"\s*{TIMECODE_PATTERN}\s*(.*)$",  # noqa: E501
    flags=re.M,
)


# Maximum gap between two adjacent events
MAXIMUM_GAP_MS = 1400


def parse_block(s: str, group: int) -> list[Event]:
    """Parses single SSMD block and extracts speech events.
    Args:
        text: speech events in SSMD format.
    Returns:
        Speech events.
    """
    events = []

    for matches in [
        timecode_parser.findall(line)
        for line in s.split("\n")
        if not line.startswith("[")
    ]:
        assert len(matches) == 1, "Invalid SSMD format"
        match = matches[0]
        event_text = match[-1]
        character_str = match[-5]
        time = match[1]
        qualifier = match[3]
        parameter = match[4]
        speech_rate_str = match[-3]

        time_ms = transcript.to_milliseconds(time)
        character = character_str.split(" ")[0]
        if not is_character(character):
            character = "Ada"

        duration_ms = None

        speech_rate = float(speech_rate_str) if speech_rate_str else 1.0

        match qualifier:
            case "/":
                if parameter:
                    finish_ms = transcript.to_milliseconds(parameter)

                    duration_ms = (
                        finish_ms - time_ms if time_ms is not None else finish_ms
                    )
            case "#":
                duration_ms = round(float(parameter) * 1000)

        events += [
            Event(
                time_ms=time_ms,
                duration_ms=duration_ms,
                chunks=[event_text.strip()],
                voice=Voice(
                    character=character,
                    speech_rate=speech_rate,
                ),
                group=group,
            )
        ]

    return [
        replace(
            event,
            duration_ms=event.duration_ms
            if event.duration_ms is not None or next_event == event
            else next_event.time_ms - event.time_ms,
        )
        for event, next_event in zip(events, events[1:] + [events[-1]])
    ]


def parse(s: str) -> Sequence[Event]:
    """Parses SSMD text and extracts speech events turning gaps into blanks."""

    blocks = [block.strip() for block in s.split("\n\n") if block]
    return no_gaps(
        sum(
            [parse_block(block, group=group) for group, block in enumerate(blocks)],
            [],
        ),
        threshold_ms=MAXIMUM_GAP_MS,
    )


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

    for event, next_event in zip(events, list(events[1:]) + [events[-1]]):
        time = (
            transcript.ms_to_iso_time(event.time_ms)[:-4]
            if event.time_ms is not None
            else ""
        )
        event_text = " ".join(event.chunks)
        event_text = text.remove_symbols(event_text, "\n")
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

        lines += [f"{time} ({voice}) {event_text}{comment}".strip()]  # noqa: E501

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
