from pathlib import Path
from uuid import uuid4

import librosa
import soundfile as sf


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
