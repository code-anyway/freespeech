import re
from itertools import zip_longest
from pathlib import Path
from uuid import uuid4

from pydub import AudioSegment, silence

from freespeech.lib import audio, speech
from freespeech.types import Event, Language, Voice

PAUSE_INCREMENT_MS = 100.0
FRAME_RATE = 44100


async def synthesize_phrase(
    phrase: str, voice: Voice, lang: Language, output_dir: Path
) -> AudioSegment:
    clip, _ = await speech.synthesize_text(
        text=phrase,
        duration_ms=None,
        voice=voice,
        lang=lang,
        output_dir=output_dir,
    )
    if phrase.strip() == "":
        return AudioSegment.empty()
    return AudioSegment.from_file(audio.strip(clip))


def detect_speech_and_pauses(seg: AudioSegment) -> tuple[list[AudioSegment], list[int]]:
    non_silent = silence.detect_nonsilent(seg, min_silence_len=25, silence_thresh=-50)
    print(non_silent)
    speech_segments = []
    pauses = []

    if not non_silent:
        return [], [len(seg)]

    if non_silent:
        pauses.append(non_silent[0][0])

    for i, (start, end) in enumerate(non_silent):
        speech_segments.append(seg[start:end])
        if i < len(non_silent) - 1:
            pauses.append(non_silent[i + 1][0] - end)
        else:
            pauses.append(len(seg) - end)

    return speech_segments, pauses


async def synthesize_text(
    text: str, duration_ms: int | None, voice: Voice, lang: Language, output_dir: Path
) -> tuple[AudioSegment, int]:
    phrases = re.split(r"(#+((\d+(\.\d+)?)#)?)", text)

    # replace & with and
    text = text.replace("&", "and")

    # Always start with a pause
    res = AudioSegment.silent(duration=int(PAUSE_INCREMENT_MS), frame_rate=FRAME_RATE)

    for phrase, pause, duration in zip_longest(
        phrases[0::5], phrases[1::5], phrases[3:5], fillvalue=""
    ):
        if duration is None or duration == "":
            pause_ms = len(pause) * PAUSE_INCREMENT_MS
        else:
            pause_ms = float(duration) * 1000

        res += await synthesize_phrase(phrase, voice, lang, output_dir)
        res += AudioSegment.silent(duration=int(pause_ms), frame_rate=FRAME_RATE)

    output_file = str(Path(output_dir) / f"{uuid4()}.wav")
    fd = res.export(output_file, format="wav")
    fd.close()  # type: ignore

    audio_segments, pauses = detect_speech_and_pauses(
        AudioSegment.from_file(output_file)
    )

    print(pauses)

    total_speech_ms = sum(map(len, audio_segments))
    total_pause_ms = sum(pauses)

    if duration_ms is None:
        duration_ms = int(total_speech_ms + total_pause_ms)

    pause_scale = (duration_ms - total_speech_ms) / total_pause_ms
    pauses = [int(pause * pause_scale) if pause_scale >= 0 else 0 for pause in pauses]

    print(pauses)

    frame_rate = (
        audio_segments[0].frame_rate
        if audio_segments and audio_segments[0].frame_rate
        else FRAME_RATE
    )

    res = AudioSegment.empty()

    for audio_segment, pause in zip_longest(audio_segments, pauses, fillvalue=None):
        if pause is not None and pause > 0:
            res += AudioSegment.silent(duration=int(pause), frame_rate=frame_rate)
        if audio_segment is not None:
            res += audio_segment

    return res, len(res) - duration_ms


async def synthesize(
    events: list[Event],
    lang: Language,
    output_dir: str,
) -> Path:
    carry_over = 0

    res = AudioSegment.empty()
    if events and events[0].time_ms is not None and events[0].time_ms > 0:
        res += AudioSegment.silent(duration=events[0].time_ms, frame_rate=FRAME_RATE)

    for i, event in enumerate(events):
        duration_ms = None

        if i < len(events) - 1:
            duration_ms = events[i + 1].time_ms - event.time_ms - carry_over

        if i == len(events) - 1:
            duration_ms = event.duration_ms

        text = " ".join(event.chunks)
        phrase, carry_over = await synthesize_text(
            text=text,
            duration_ms=duration_ms,
            voice=event.voice,
            lang=lang,
            output_dir=Path(output_dir),
        )
        res += phrase

    output_file = str(Path(output_dir) / f"{uuid4()}.wav")
    fd = res.export(output_file, format="wav")
    fd.close()  # type: ignore

    if events[-1].time_ms is not None and events[-1].duration_ms is not None:
        total_duration_ms = events[-1].time_ms + events[-1].duration_ms
        if total_duration_ms != len(res):
            output_file = audio.resample(output_file, total_duration_ms, output_dir)

    return Path(output_file)
