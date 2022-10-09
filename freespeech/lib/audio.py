import librosa
import soundfile as sf
from pathlib import Path


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
        sf.write(fd, signal[start:end], rate, subtype='PCM_16')

    return file
