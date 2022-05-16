from datetime import time
from pathlib import Path
import re
from typing import Sequence
from freespeech.types import Event


def to_milliseconds(t: time) -> int:
    return (
        t.hour * 60 * 60 * 1_000
        + t.minute * 60 * 1_000
        + t.second * 1_000
        + t.microsecond // 1_000
    )


def to_time(s: str) -> time:
    return time.fromisoformat(str.replace(s, ",", "."))


def srt(srt_file: Path | str) -> Sequence[Event]:
    with open(srt_file, "r") as fd:
        text = "".join(list(fd)) + "\n"

    parser = re.compile(r"\d+\n([\d\:\,]+)\s*-->\s*([\d\:\,]+)\n((.+\n)+)")
    match = parser.findall(text)

    result = [
        Event(
            time_ms=(start_ms := to_milliseconds(to_time(start))),
            duration_ms=(to_milliseconds(to_time(finish)) - start_ms),
            chunks=[(" ".join(text.split("\n"))).strip()],
        )
        for start, finish, text, _ in match
    ]

    return result
