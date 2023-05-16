import re
from pathlib import Path
from tempfile import TemporaryDirectory

from pydub import AudioSegment

from freespeech.lib import speech
from freespeech.types import Event, Language

PAUSE_INCREMENT_MS = 50


async def synthesize(
    events: list[Event],
    lang: Language,
    sentence_pause_ms: int,
    min_rate: float,
    min_silence_scale: float,
    variance_threshold: float,
    output_dir: str,
) -> Path:
    segments: list[AudioSegment] = []

    with TemporaryDirectory() as output_dir:
        for i, event in enumerate(events):
            duration_ms = None
            if i < len(events) - 1:
                duration_ms = events[i + 1].time_ms - event.time_ms

            phrase_text = " ".join(event.chunks)
            # Use regexp to split phrase_text using #+ as separator
            # to get a list of phrases
            phrases = re.split(r"(#+)", phrase_text)
            for phrase in phrases:
                if phrase.startswith("#"):
                    pause_ms = len(phrase) * PAUSE_INCREMENT_MS
                    segments.append(AudioSegment.silent(duration=pause_ms))
                else:
                    clip, _ = await speech.synthesize_text(
                        text=phrase,
                        duration_ms=None,
                        voice=event.voice,
                        lang=lang,
                        output_dir=output_dir,
                    )
                    segments.append(AudioSegment.from_file(clip))
