import re
from dataclasses import dataclass
from functools import reduce
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory

from freespeech.lib import audio, media, speech, text
from freespeech.types import Character, Event, Language, Voice


@dataclass(frozen=True)
class Interval:
    speech_ms: int
    rate: float
    silence_scale: float
    character: Character
    outline: list[str | int]


def normalize(outline: list[str | int]) -> list[str | int]:
    def reducer(x: list[str | int], y: str | int) -> list[int | str]:
        if x and isinstance(x[-1], int) and isinstance(y, int):
            return x[:-1] + [x[-1] + y]
        else:
            return x + [y]

    return reduce(reducer, outline, [])


def _silence(outline: list[int | str]) -> int:
    return sum(item for item in outline if isinstance(item, int))


def merge(a: Interval, b: Interval) -> Interval:
    speech_ms = a.speech_ms + b.speech_ms
    rate = (a.rate * a.speech_ms + b.rate * b.speech_ms) / speech_ms

    silence_ms = _silence(a.outline + b.outline)

    if silence_ms == 0:
        silence_scale = 1.0
    else:
        silence_scale = (
            _silence(a.outline) * a.silence_scale
            + _silence(b.outline) * b.silence_scale
        ) / silence_ms

    if a.character != b.character:
        raise ValueError("character in a and b should be the same")

    return Interval(
        speech_ms=speech_ms,
        rate=rate,
        silence_scale=silence_scale,
        outline=normalize(
            a.outline + b.outline,
        ),
        character=a.character,
    )


def adjust(
    interval: Interval, target_rate: float, min_silence_scale: float
) -> Interval:
    """Brings speech rate and silence_scale of an interval to match target speech rate.

    Args:
        interval: Speech interval.
        target_rate: Target speech rate.
        min_silence_scale: Minimum scale factor for pauses.

    Returns:
        New speech interval with speech rate as close to target_rate as possible
        while minimum pause scale factor.
    """
    if interval.speech_ms == 0:
        return Interval(
            speech_ms=0,
            rate=target_rate,
            silence_scale=interval.silence_scale,
            outline=interval.outline,
            character=interval.character,
        )

    target_scale_factor = interval.rate / target_rate
    speech = interval.speech_ms * target_scale_factor
    silence_ms = _silence(interval.outline) * interval.silence_scale
    # Don't shrink pauses below min_silence_scale.
    silence_scale = max(
        min_silence_scale,
        (silence_ms - (speech - interval.speech_ms)) / _silence(interval.outline),
    )
    speech_ms = round(
        interval.speech_ms + silence_ms - _silence(interval.outline) * silence_scale
    )

    scale_factor = interval.speech_ms / speech_ms
    rate = interval.rate * scale_factor

    new_interval = Interval(
        speech_ms=speech_ms,
        rate=rate,
        silence_scale=silence_scale,
        character=interval.character,
        outline=interval.outline,
    )

    old_interval_duration = round(
        interval.speech_ms + _silence(interval.outline) * interval.silence_scale
    )
    new_interval_duration = round(
        new_interval.speech_ms
        + _silence(new_interval.outline) * new_interval.silence_scale
    )

    assert (
        abs(old_interval_duration - new_interval_duration) <= 1
    ), f"Adjustment resulted in different durations: old={old_interval_duration}, new={new_interval_duration}"  # noqa: E501

    return new_interval


def get_outline(s: str, sentence_pause_ms: int, lang: Language) -> list[str | int]:
    split = re.split(r"#(\d+(\.\d+)?)#", s)
    sentences_and_pauses: list[list[int | str]] = [
        [
            # Interlace each sentence with pauses.
            *sum(
                [
                    [sentence_pause_ms, sentence]
                    for sentence in text.sentences(sentence.strip(), lang=lang)
                ],
                [],
            )[1:],
            round((float(pause) if pause else 0.0) * 1000),
        ]
        for sentence, pause in zip_longest(split[0::3], split[1::3], fillvalue="")
        if sentence or pause
    ]

    outline: list[str | int] = [item for item in sum(sentences_and_pauses, []) if item]

    # Add leading pause.
    if outline and not isinstance(outline[0], int):
        outline = [sentence_pause_ms, *outline]

    return normalize(outline)


async def get_interval(
    event: Event, sentence_pause_ms: int, lang: Language
) -> Interval:
    if event.duration_ms is None:
        raise ValueError("event.duration_ms must be set")

    paragraph = " ".join(event.chunks)
    outline: list[str | int] = get_outline(
        paragraph, sentence_pause_ms=sentence_pause_ms, lang=lang
    )
    if outline == []:
        outline = [event.duration_ms]

    with TemporaryDirectory() as tmp_dir:
        clips = [
            audio.strip(
                (
                    await speech.synthesize_text(
                        text=chunk,
                        duration_ms=None,
                        voice=event.voice,
                        lang=lang,
                        output_dir=tmp_dir,
                    )
                )[0]
            )
            if isinstance(chunk, str)
            else chunk
            for chunk in outline
        ]

        speech_ms = sum(audio.duration(clip) for clip in clips if isinstance(clip, str))

        if event.duration_ms:
            silence_ms = event.duration_ms - speech_ms
            silence_scale = silence_ms / _silence(outline)
        else:
            silence_ms = _silence(outline)
            silence_scale = 1.0

    interval = Interval(
        speech_ms=speech_ms,
        rate=event.voice.speech_rate,
        silence_scale=silence_scale,
        character=event.voice.character,
        outline=outline,
    )

    return interval


def average_rate(intervals: list[Interval]) -> float:
    total_speech_ms = sum(interval.speech_ms for interval in intervals)
    return (
        sum(interval.rate * interval.speech_ms for interval in intervals)
        / total_speech_ms
    )


def patch(
    intervals: list[Interval], index: int, target_rate: float, min_silence_scale: float
) -> list[Interval]:
    """Patch the interval sequence at the given index to achieve target speech rate.

    Args:
        intervals: Input sequence of intervals.
        index: index to patch around.
        target_rate: target speech rate.
        min_silence_scale: Minimum scale factor for pauses.

    Returns:
        Initial sequence of intervals with the interval at index i merge with
        previous or next one to reduce the speech rate.
    """
    if len(intervals) <= 1:
        return intervals

    def merge_and_adjust(a: Interval, b: Interval) -> Interval:
        return adjust(
            merge(a, b), target_rate=target_rate, min_silence_scale=min_silence_scale
        )

    if index == 0:
        return [merge_and_adjust(intervals[index], intervals[index + 1])] + intervals[
            2:
        ]

    if index == len(intervals) - 1:
        return intervals[:-2] + [
            merge_and_adjust(intervals[index - 1], intervals[index])
        ]

    _next = merge_and_adjust(intervals[index], intervals[index + 1])
    _prev = merge_and_adjust(intervals[index - 1], intervals[index])

    if _prev.rate < _next.rate:
        return intervals[: index - 1] + [_prev] + intervals[index + 1 :]
    else:
        return intervals[:index] + [_next] + intervals[index + 2 :]


def smoothen(
    intervals: list[Interval], min_silence_scale: float, variance_threshold: float
) -> list[Interval]:
    average = average_rate(intervals)
    intervals = [
        adjust(
            interval,
            target_rate=average,
            min_silence_scale=min_silence_scale,
        )
        for interval in intervals
    ]

    while True:
        value, index = max((interval.rate, i) for i, interval in enumerate(intervals))
        if (value - average) > average * variance_threshold:
            intervals = patch(
                intervals=intervals,
                index=index,
                target_rate=average,
                min_silence_scale=min_silence_scale,
            )
        else:
            return intervals


async def synthesize_intervals(
    intervals: list[Interval], lang: Language, output_dir: str
) -> str:
    clips = []

    for interval in intervals:
        for item in interval.outline:
            if isinstance(item, str):
                clips += [
                    audio.strip(
                        str(
                            (
                                await speech.synthesize_text(
                                    text=item,
                                    duration_ms=None,
                                    voice=Voice(
                                        character=interval.character,
                                        speech_rate=interval.rate,
                                    ),
                                    output_dir=output_dir,
                                    lang=lang,
                                )
                            )[0]
                        )
                    )
                ]
            elif isinstance(item, int):
                clips += [
                    audio.silence(
                        int(item * interval.silence_scale), output_dir=output_dir
                    )
                ]

    return str(await media.concat(clips=clips, output_dir=output_dir))


async def synthesize_block(
    events: list[Event],
    lang: Language,
    sentence_pause_ms: int,
    min_rate: float,
    min_silence_scale: float,
    variance_threshold: float,
    output_dir: str,
) -> str:
    intervals = [
        await get_interval(event, sentence_pause_ms=sentence_pause_ms, lang=lang)
        for event in events
    ]

    adjusted_intervals = [
        adjust(interval, target_rate=min_rate, min_silence_scale=min_silence_scale)
        for interval in intervals
    ]

    def interval_event_delta(event: Event, interval: Interval) -> int:
        if event.duration_ms is None:
            return True

        return round(
            event.duration_ms
            - interval.speech_ms
            - _silence(interval.outline) * interval.silence_scale
        )

    for event, interval in zip(events, adjusted_intervals):
        delta = interval_event_delta(event, interval)
        assert (
            abs(delta) <= 1
        ), f"Event duration mismatch (d={delta}): {event} {interval}"  # noqa: E501

    smooth_intervals = smoothen(
        adjusted_intervals,
        min_silence_scale=min_silence_scale,
        variance_threshold=variance_threshold,
    )

    clip = await synthesize_intervals(
        smooth_intervals, lang=lang, output_dir=output_dir
    )

    block_duration_ms = 0
    for event in events:
        assert event.duration_ms is not None, f"Event duration is not set for {event}"
        block_duration_ms += event.duration_ms

    return audio.resample(
        audio_file=clip,
        target_duration_ms=block_duration_ms,
        output_dir=output_dir,
    )


def separate_events(events: list[Event]) -> list[list[Event]]:
    """Separate events into blocks based on group change,
    speaker change or if silence.
    """
    blocks: list[list[Event]] = []
    for event in events:
        if (
            not blocks
            or blocks[-1][-1].voice != event.voice
            or blocks[-1][-1].group != event.group
            or not any(blocks[-1][-1].chunks)
        ):  # silence
            blocks.append([])
        blocks[-1].append(event)
    return blocks


async def synthesize(
    events: list[Event],
    lang: Language,
    sentence_pause_ms: int,
    min_rate: float,
    min_silence_scale: float,
    variance_threshold: float,
    output_dir: str,
) -> Path:
    clips = []
    blocks = separate_events(events)

    for block in blocks:
        clip = await synthesize_block(
            block,
            lang=lang,
            sentence_pause_ms=sentence_pause_ms,
            min_rate=min_rate,
            min_silence_scale=min_silence_scale,
            variance_threshold=variance_threshold,
            output_dir=output_dir,
        )

        for event in block:
            if event.duration_ms is None:
                raise ValueError(f"Event duration is not set for: {event}")

        clips += [clip]

    previous_block_end_ms = 0
    gaps = []

    for events in blocks:
        first = events[0]
        last = events[-1]

        gaps += [first.time_ms - previous_block_end_ms]

        if last.duration_ms is None:
            raise ValueError(f"Event duration is not set for: {last}")

        previous_block_end_ms = last.time_ms + last.duration_ms

    audio_files: list[str] = sum(
        [
            [str(audio.silence(gap, output_dir=output_dir)), str(speech_file)]
            for gap, speech_file in zip(gaps, clips)
        ],
        [],
    )

    return await media.concat(clips=audio_files, output_dir=output_dir)
