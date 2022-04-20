import logging
import uuid
from os import PathLike
from pathlib import Path
from typing import Dict, Sequence, Tuple

import ffmpeg

from freespeech.lib import concurrency
from freespeech.types import Audio, AudioEncoding, Video, VideoEncoding

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


def probe(file: str | PathLike) -> Tuple[Sequence[Audio], Sequence[Video]]:
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

    def parse_stream(stream: Dict, format: Dict) -> Audio | Video | None:
        duration = stream.get("duration", None) or format.get("duration", None)
        assert duration, "Couldn't infer duration from stream or format"
        duration_ms = int(float(duration) * 1000)

        match stream["codec_type"]:
            case "audio":
                return Audio(
                    duration_ms=duration_ms,
                    encoding=ffprobe_to_audio_encoding(stream["codec_name"]),
                    sample_rate_hz=int(stream["sample_rate"]),
                    num_channels=stream["channels"],
                )
            case "video":
                return Video(
                    duration_ms=duration_ms,
                    encoding=ffprobe_to_video_encoding(stream["codec_name"]),
                )
            case codec_type:
                logger.warning(f"Unsupported codec type: {codec_type}")
                return None

    streams = info["streams"]
    format = info["format"]

    streams = [info for s in streams if (info := parse_stream(s, format))]

    return (
        [s for s in streams if isinstance(s, Audio)],
        [s for s in streams if isinstance(s, Video)],
    )


def new_file(dir: str | PathLike) -> PathLike:
    return Path(dir) / str(uuid.uuid4())


async def multi_channel_audio_to_mono(
    file: str | PathLike, output_dir: str | PathLike
) -> Path:
    """Convert multi-channel audio to mono by downmixing.

    Args:
        file: path to a local file containing audio stream.
        output_dir: directory to store the conversion result.

    Return:
        A path to a newly generated audio file.
    """
    file = Path(file)
    output_dir = Path(output_dir)

    (audio), _ = probe(file)

    if len(audio) > 1:
        logger.warning(f"Multiple audio streams in {file}: {audio}")

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(
        ffmpeg.input(file).audio,
        filename=output_file,
        ac=1,  # audio channels = 1
    )

    await _run(pipeline)

    return output_file


async def concat_and_pad(
    clips: Sequence[Tuple[int, str | PathLike]], output_dir: str | PathLike
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
        for time_ms, file in clips
        if (audio := ffmpeg.input(file).audio)
    ]

    # TODO astaff (20220311): not specifying v and a gives a weird error
    # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
    stream = ffmpeg.concat(*inputs, v=0, a=1)

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(stream, filename=output_file)

    await _run(pipeline)

    return output_file


async def concat(clips: Sequence[str], output_dir: str | PathLike) -> Path:
    """Concatenate audio clips.

    Args:
        clips: list of paths to audio files.
        output_dir: directory to store the conversion result.

    Returns:
        Path to audio file with concatenated clips.
    """
    return await concat_and_pad([(0, clip) for clip in clips], output_dir)


async def mix(
    files: Sequence[str | PathLike], weights: Sequence[int], output_dir: str | PathLike
) -> Path:
    """Mix multiple audio files into a single file.

    Args:
        files: files to mix.
        weights: weight of each file in the resulting mix.
        output_dir: directory to store the conversion result.

    Returns:
        Audio file with all files normalized and mixed according to weights.
    """
    audio_streams = [ffmpeg.input(file).audio for file in files]
    mixed_audio = ffmpeg.filter(
        audio_streams,
        filter_name="amix",
        weights=" ".join(str(weight) for weight in weights),
    )

    output_file = Path(f"{new_file(output_dir)}.wav")
    pipeline = ffmpeg.output(mixed_audio, filename=output_file)

    await _run(pipeline)

    return output_file


async def dub(
    video: str | PathLike, audio: str | PathLike, output_dir: str | PathLike
) -> Path:
    streams = (ffmpeg.input(audio).audio, ffmpeg.input(video).video)

    video = Path(video)
    output_file = Path(f"{new_file(output_dir)}{video.suffix}")
    pipeline = ffmpeg.output(*streams, filename=output_file)

    await _run(pipeline)

    return output_file


async def _run(pipeline):
    try:

        def _run_pipeline():
            pipeline.run(overwrite_output=True, capture_stderr=True)

        await concurrency.run_in_thread_pool(_run_pipeline)
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg Error stderr: {e.stderr}")
