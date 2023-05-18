import re
from pathlib import Path
from uuid import uuid4

from pydub import AudioSegment

from freespeech.lib import audio, speech
from freespeech.types import Event, Language, Voice

PAUSE_INCREMENT_MS = 100.0


async def synthesize_text(
    text: str, duration_ms: int | None, voice: Voice, lang: Language, output_dir: Path
) -> tuple[AudioSegment, int]:
    phrases = re.split(r"(#+)", text)
    segments: list[AudioSegment | float] = [PAUSE_INCREMENT_MS]

    for phrase in phrases:
        if phrase.startswith("#"):
            pause_ms = len(phrase) * PAUSE_INCREMENT_MS
            segments.append(pause_ms)
        else:
            clip, _ = await speech.synthesize_text(
                text=phrase,
                duration_ms=None,
                voice=voice,
                lang=lang,
                output_dir=output_dir,
            )
            segments.append(AudioSegment.from_file(audio.strip(clip)))
    segments.append(PAUSE_INCREMENT_MS)

    total_speech_ms = sum(
        [len(segment) for segment in segments if isinstance(segment, AudioSegment)]
    )
    total_pause_ms = sum(
        [segment for segment in segments if isinstance(segment, float)]
    )

    if duration_ms is None:
        duration_ms = int(total_speech_ms + total_pause_ms)

    pause_scale = (duration_ms - total_speech_ms) / total_pause_ms
    if pause_scale >= 0:
        segments = [
            segment * pause_scale if isinstance(segment, float) else segment
            for segment in segments
        ]
    else:
        segments = [
            segment if isinstance(segment, AudioSegment) else 0 for segment in segments
        ]

    frame_rate = 44100
    audio_segments = [
        segment for segment in segments if isinstance(segment, AudioSegment)
    ]
    if audio_segments and audio_segments[0].frame_rate:
        frame_rate = audio_segments[0].frame_rate

    res = AudioSegment.empty()
    for segment in segments:
        if isinstance(segment, AudioSegment):
            res += segment
        else:
            if segment > 0:
                res += AudioSegment.silent(duration=int(segment), frame_rate=frame_rate)

    return res, len(res) - duration_ms


async def synthesize(
    events: list[Event],
    lang: Language,
    output_dir: str,
) -> Path:
    carry_over = 0
    res = AudioSegment.empty()

    for i, event in enumerate(events):
        duration_ms = None
        if i < len(events) - 1:
            duration_ms = events[i + 1].time_ms - event.time_ms - carry_over
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
    res.export(output_file, format="wav")

    return Path(output_file)
