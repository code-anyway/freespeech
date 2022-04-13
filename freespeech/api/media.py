import logging
import uuid
from pathlib import Path
from typing import Dict, Sequence, Tuple

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
        case "hevc":
            return "HEVC"
        case invalid_encoding:
            raise ValueError(f"Invalid encoding: {invalid_encoding}")


def probe(file: path) -> Tuple[Sequence[Audio], Sequence[Video]]:
    """Get a list of Audio and Video streams for a file.

    Args:
        file: path to a local file.

    Returns:
        Tuple of lists of `Audio` and `Video` stream information.
    """

    try:
        info = ffmpeg.probe(file)
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg error: {e.stderr}")

    def parse_stream(stream: Dict) -> Audio | Video | None:
        match stream["codec_type"]:
            case "audio":
                return Audio(
                    duration_ms=int(float(stream["duration"]) * 1000),
                    encoding=ffprobe_to_audio_encoding(stream["codec_name"]),
                    sample_rate_hz=int(stream["sample_rate"]),
                    num_channels=stream["channels"],
                )
            case "video":
                return Video(
                    duration_ms=int(float(stream["duration"]) * 1000),
                    encoding=ffprobe_to_video_encoding(stream["codec_name"]),
                )
            case codec_type:
                logger.warning(f"Unsupported codec type: {codec_type}")
                return None

    streams = [info for s in info["streams"] if (info := parse_stream(s))]

    return (
        [s for s in streams if isinstance(s, Audio)],
        [s for s in streams if isinstance(s, Video)]
    )


def new_file(dir: path) -> Path:
    return Path(dir) / str(uuid.uuid4())


def multi_channel_audio_to_mono(file: path, output_dir: path) -> Path:
    """Convert multi-channel audio to mono by downmixing.

    Args:
        file: path to a local file containing audio stream.
        output_dir: directory to store the conversion result.

    Return:
        A path to a newly generated audio file.
    """
    file = Path(file)
    output_dir = Path(output_dir)

    (audio, *tail), _ = probe(file)

    if tail:
        logger.warning(f"Additional audio streams in {file}: {tail}")

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(
        ffmpeg.input(file).audio,
        filename=output_file,
        ac=1,  # audio channels = 1
    )

    try:
        pipeline.run(overwrite_output=True, capture_stderr=True)
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg Error stderr: {e.stderr}")

    return output_file


def concat_and_pad(
    clips: Sequence[Tuple[int, path]],
    output_dir: path
) -> Path:
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

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(stream, filename=output_file)

    try:
        pipeline.run(overwrite_output=True, capture_stderr=True)
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg Error stderr: {e.stderr}")

    return output_file


def concat(clips: Sequence[str], output_dir: path) -> Path:
    """Concatenate audio clips.

    Args:
        clips: list of paths to audio files.
        output_dir: directory to store the conversion result.

    Returns:
        Path to audio file with concatenated clips.
    """
    return concat_and_pad([(0, clip) for clip in clips], output_dir)


def mix(clips: Sequence[Tuple[path, int]], output_dir: path) -> Path:
    """Mix multiple audio files into a single file.

    Args:
        clips: list of (path, weight) of clips to mix.
        output_dir: directory to store the conversion result.

    Returns:
        Audio file with all clips normalized and mixed according to weights.
    """
    audio_streams = [ffmpeg.input(file).audio for file, _ in clips]
    weights = " ".join(str(weight) for _, weight in clips)
    print(weights)
    mixed_audio = ffmpeg.filter(audio_streams, "amix", weights=weights)

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(mixed_audio, filename=output_file)
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file


def dub(video: path, audio: path, output_dir: path) -> Path:
    streams = (ffmpeg.input(audio).audio, ffmpeg.input(video).video)

    video = Path(video)
    output_file = Path(f"{new_file(output_dir)}{video.suffix}")
    pipeline = ffmpeg.output(*streams, filename=output_file)
    pipeline.run(overwrite_output=True, capture_stderr=True)

    return output_file
