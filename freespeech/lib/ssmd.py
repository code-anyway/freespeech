import re
from dataclasses import replace
from typing import List, Sequence

from freespeech.lib import text, transcript
from freespeech.types import Event, Voice

timecode_parser = re.compile(
    r"(^\s*(([\d\:\.]+)?\s*(([/#])\s*([\d\:\.]+))?\s*(\((.+?)(@(\d+(\.\d+)?))?\)))\s*(.+)$)+",  # noqa: E501
    flags=re.M,
)


def parse(s: str) -> Sequence[Event]:
    """ "Parses SSMD body and extracts speech events.

    Args:
        text: speech events in SSMD format.

    Returns:
        Speech events.
    """
    matches = timecode_parser.findall(s)
    events = []

    for match in matches:
        event_text = match[-1]
        character_str = match[-5]
        time = match[2]
        qualifier = match[4]
        parameter = match[5]
        speech_rate_str = match[-3]

        time_ms = transcript.to_milliseconds(time) if time else None
        character = character_str.split(" ")[0] if character_str else None
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
                chunks=[event_text],
                voice=Voice(
                    character=character,
                    speech_rate=speech_rate,
                ),
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


def align(events: List[Event]) -> Sequence[Event]:
    """Transforms a sequence of events adjusting durations so that the end of each event
    matches the beginning of a next one. Adds speech pauses in the end.

    Args:
        events: events to be adjusted.

    Returns:
        Sequence of events where for each event time_ms + duration_ms
        equals time_ms of the next one.
    """

    return [
        replace(
            event,
            duration_ms=(new_duration_ms := next_event.time_ms - event.time_ms),
            chunks=[
                " ".join(event.chunks)
                + (
                    ""
                    if (pause_ms := new_duration_ms - event.duration_ms) <= 0
                    else f" #{pause_ms / 1000:.1f}#"
                )
            ],
        )
        for event, next_event in zip(events[:-1], events[1:])
    ] + [events[-1]]


def render(events: Sequence[Event]) -> str:
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

        lines += [
            f"{time} ({event.voice.character}@{event.voice.speech_rate:.1f}) {event_text}"  # noqa: E501
        ]

    return "\n".join(lines)
