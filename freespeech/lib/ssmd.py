import re
from typing import Sequence

from freespeech.lib import transcript
from freespeech.types import Event, Voice

timecode_parser = re.compile(
    r"(^\s*(([\d\:\.]+)?\s*(([/#@])\s*([\d\:\.]+))?\s*(\((.+)\)))\s*(.+)$)+", flags=re.M
)


def parse(text: str) -> Sequence[Event]:
    """ "Parses SSMD body and extracts speech events.

    Args:
        text: speech events in SSMD format.

    Returns:
        Speech events.
    """
    matches = timecode_parser.findall(text)
    events = []

    for match in matches:
        text = match[-1]
        character_str = match[-2]
        time = match[2]
        qualifier = match[4]
        parameter = match[5]

        time_ms = transcript.to_milliseconds(time) if time else None
        character = character_str.split(" ")[0] if character_str else None
        duration_ms = None
        speech_rate = 1.0

        match qualifier:
            case "/":
                if parameter:
                    finish_ms = transcript.to_milliseconds(parameter)

                    duration_ms = (
                        finish_ms - time_ms if time_ms is not None else finish_ms
                    )
            case "#":
                duration_ms = round(float(parameter) * 1000)
            case "@":
                speech_rate = float(parameter)

        events += [
            Event(
                time_ms=time_ms,
                duration_ms=duration_ms,
                chunks=[text],
                voice=Voice(
                    character=character,
                    speech_rate=speech_rate,
                ),
            )
        ]

    return events
