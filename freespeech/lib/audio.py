from pathlib import Path
from uuid import uuid4

import librosa
import soundfile as sf

from freespeech.lib import media


def duration(file: Path | str) -> int:
    signal, rate = librosa.load(file)
    return round((len(signal) / rate) * 1000.0)


def resample(audio_file: str, target_duration_ms: int, output_dir: str) -> str:
    signal, sr = librosa.load(audio_file)
    original_duration_ms = duration(audio_file)
    new_sr = sr * (target_duration_ms / original_duration_ms)
    new_signal = librosa.resample(signal, orig_sr=sr, target_sr=new_sr)

    output_file = f"{media.new_file(output_dir)}.wav"

    with open(output_file, "wb") as fd:
        sf.write(fd, new_signal, sr, subtype="PCM_16")

    return output_file


def strip(file: Path | str) -> Path | str:
    """Removes silence in the beginning and in the end of audio file.
    This function will overwrite the original file.
    Args:
        file: Input audio file.
    Returns:
        *Same* audio file. It will overwrite the original one.
    """
    with open(file, "rb") as fd:
        signal, rate = librosa.load(fd)

    _, (start, end) = librosa.effects.trim(signal)

    with open(file, "wb") as fd:
        sf.write(fd, signal[start:end], rate, subtype="PCM_16")

    return file


def silence(duration_ms: int, output_dir: str) -> Path:
    sample_rate = 44100
    signal = [0.0] * round((duration_ms / 1000.0) * sample_rate)
    file = Path(output_dir) / f"{uuid4()}.wav"
    sf.write(file=str(file), data=signal, samplerate=sample_rate, subtype="PCM_16")
    return file
