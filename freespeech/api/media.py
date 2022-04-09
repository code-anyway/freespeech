import logging
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import ffmpeg

from freespeech.types import Audio, AudioEncoding, Video, VideoEncoding, path

logger = logging.getLogger(__name__)


def ffprobe_to_audio_encoding(encoding: str) -> AudioEncoding:
    """Convert ffprobe audio encoding to `AudioEncoding`."""
    match encoding:
        case "opus":
            return "WEBM_OPUS"
        case "pcm_s16le":
            return "LINEAR16"
        case "aac":
            return "AAC"
        case invalid_encoding:
            raise ValueError(f"Invalid encoding: {invalid_encoding}")


def ffprobe_to_video_encoding(encoding: str) -> VideoEncoding:
    """Convert ffprobe video encoding to `VideoEncoding`."""
    match encoding:
        case "h264":
            return "H264"
        case invalid_encoding:
            raise ValueError(f"Invalid encoding: {invalid_encoding}")


def probe(file: path) -> List[Audio | Video]:
    """Get a list of Audio and Video streams for a file.

    Args:
        file: path to a local file.

    Returns:
        List of `Audio` and `Video` with stream information.
    """
    info = ffmpeg.probe(file)

    def parse_stream(stream: Dict) -> Audio | Video:
        match stream["codec_type"]:
            case "audio":
                return Audio(
                    duration_ms=int(float(info["format"]["duration"]) * 1000),
                    encoding=ffprobe_to_audio_encoding(stream["codec_name"]),
                    sample_rate_hz=int(stream["sample_rate"]),
                    num_channels=stream["channels"],
                    ext=stream["extension"],
                )
            case "video":
                return Video(
                    duration_ms=int(float(info["format"]["duration"]) * 1000),
                    encoding=ffprobe_to_video_encoding(stream["codec_name"]),
                    ext=stream["extension"],
                )
            case codec_type:
                raise ValueError(f"Unsupported codec type: {codec_type}")

    return [parse_stream(s) for s in info["streams"]]


def new_file(dir: path) -> Path:
    return Path(dir) / str(uuid.uuid4())


def multi_channel_audio_to_mono(file: path, output_dir: path) -> path:
    """Convert multi-channel audio to mono by downmixing.

    Args:
        file: path to a local file containing audio stream.
        output_dir: directory to store the conversion result.

    Return:
        A path to a newly generated audio file.
    """
    file = Path(file)
    output_dir = Path(output_dir)

    streams = probe(file)
    audio, *_ = [stream for stream in streams if isinstance(stream, Audio)]

    if _:
        logger.warn(f"Additional audio streams in {file}: {_}")

    if audio.num_channels == 1:
        return file

    pipeline = ffmpeg.output(
        ffmpeg.input(file).audio,
        output_file := new_file(output_dir),
        ac=1,  # audio channels = 1
    )
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file


def concat_and_pad(clips: List[Tuple[int, path]], output_dir: path) -> path:
    """Concatenate audio clips and add padding.

    Args:
        clips: list of tuples (pad_ms, file).
            pad_ms is how much padding to add before the clip stored in file.
        output_dir: directory to store the conversion result.

    Returns:
        Path to audio file with concatenated clips and padding added.
    """
    output_dir = Path(output_dir)

    # "adelay" errors out if duration is 0
    inputs = [
        audio.filter("adelay", delays=time_ms) if time_ms != 0 else audio
        for time_ms, file in clips if (audio := ffmpeg.input(file).audio)
    ]

    # TODO astaff (20220311): not specifying v and a gives a weird error
    # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
    stream = ffmpeg.concat(*inputs, v=0, a=1)

    pipeline = ffmpeg.output(stream, output_file := new_file(output_dir))
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file


def concat(clips: List[str], output_dir: path) -> path:
    """Concatenate audio clips.

    Args:
        clips: list of paths to audio files.
        output_dir: directory to store the conversion result.

    Returns:
        Path to audio file with concatenated clips.
    """
    return concat_and_pad([(0, clip) for clip in clips], output_dir)


def mix(clips: List[Tuple[path, int]], output_dir: path) -> path:
    """Mix multiple audio files into a single file.

    Args:
        clips: list of weighted audio clips to mix.
        output_dir: directory to store the conversion result.

    Returns:
        Audio file with all clips normalized and mixed according to weights.
    """
    audio_streams = (ffmpeg.input(file).audio for file, _ in clips)
    weights = " ".join(str(weight) for _, weight in clips)
    mixed_audio = ffmpeg.filter(audio_streams, "amix", weights=weights)

    pipeline = ffmpeg.output(mixed_audio, output_file := new_file(output_dir))
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file


def dub(video: path, audio: path, output_dir: path) -> path:
    streams = (ffmpeg.input(audio).audio, ffmpeg.input(video).video)
    pipeline = ffmpeg.output(*streams, output_file := new_file(output_dir))
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file
