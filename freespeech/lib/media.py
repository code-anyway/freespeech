import logging
import uuid
from os import PathLike, system
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Literal, Sequence, Tuple

import ffmpeg

from freespeech.lib import concurrency
from freespeech.types import Audio, AudioEncoding, Video, VideoEncoding, assert_never

logger = logging.getLogger(__name__)

# either an event or lack of an event, with start & end time.
Span = Tuple[str, int, int]


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
        case "av1":
            return "AV1"
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
        duration = stream.get("duration", None) or format.get("duration", None) or 0.0
        assert duration is not None, "Couldn't infer duration from stream or format"
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
    file: str | PathLike,
    output_dir: str | PathLike,
    sample_rate: int = 16_000,
) -> Path:
    """Convert multi-channel audio to mono by downmixing.

    Args:
        file: path to a local file containing audio stream.
        output_dir: directory to store the conversion result.
        sample_rate: output audio sample rate. (default: 16 kHz)

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
        acodec="pcm_s16le",
        ar=sample_rate,
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
        audio.filter("adelay", delays=time_ms) if time_ms > 0 else audio
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
    files: Sequence[str | PathLike],
    weights: Sequence[int],
    output_dir: str | PathLike,
) -> Path:
    """Mix multiple audio files into a single file.

    Args:
        files: files to mix.
        weights: weight of each file in the resulting mix.
        output_dir: directory to store the conversion result.

    Returns:
        Audio file with all files normalized and mixed according to weights.
    """
    files = [file for file in files if file]
    if len(files) == 1:
        return Path(files[0])

    audio_streams = [ffmpeg.input(file).audio for file in files if file]

    mixed_audio = amix_streams(streams=audio_streams, weights=weights)

    return await write_streams(
        streams=[mixed_audio], output_dir=output_dir, extension="wav"
    )


def trim_audio(file: str | PathLike, start_ms: int, end_ms: int):
    """Creates an ffmpeg stream from a file, then trims the audio

    Args:
        file: path to a local file containing audio stream.
        start_ms: start of cut in ms.
        end_ms: end of cut in ms.


    Return:
        The trimmed stream
    """
    audio_stream = ffmpeg.input(file).audio
    return audio_stream.filter_(
        "atrim", start=str(start_ms) + "ms", end=str(end_ms) + "ms"
    )


def trim_video(file: str | PathLike, start_ms: int, end_ms: int):
    """Creates an ffmpeg stream from a file, then trims the video

    Args:
        file: path to a local file containing video
        start_ms: start of cut in ms.
        end_ms: end of cut in ms.


    Return:
        The trimmed stream
    """
    video_stream = ffmpeg.input(file)
    return video_stream.trim(start=str(start_ms) + "ms", end=str(end_ms) + "ms")


async def write_streams(
    streams: list, output_dir: str | PathLike, extension: str, args={}
) -> Path:
    """writes a list of streams to a directory

    Args:
        streams: list of streams that'll be written to a file in output_dir
        output_dir: directory in which the file will be created.
        extension: file extension for the stream.
        args: optional, dict of args to pass into ffmpeg output.


    Return:
        The path of the file in the directory.
    """
    output_file = Path(f"{new_file(output_dir)}.{extension}")
    pipeline = ffmpeg.output(*streams, **args, filename=output_file)
    await _run(pipeline)

    return output_file


def amix_streams(streams: list, weights: Sequence[int]):
    return ffmpeg.filter(
        streams,
        filter_name="amix",
        weights=" ".join(str(weight) for weight in weights),
    )


def mix_events(
    original: str | PathLike,
    synth_file: str | PathLike,
    spans: list[Span],
    weights: Sequence,
):
    """Mixes original and synth_file, but only between event spans, otherwise uses
    original.

    Args:
        original: path to file /w original sound,
        synth_file: path to file /w dub,
        spans: spans with events and blanks,
        weights: real_weight, synth_weight,


    Return:
        A stream with everything mixed and concatenated.
    """
    # returns a list of streams
    bundle = []
    for t, start, end in spans:
        real_trim = trim_audio(original, start, end)
        match t:
            case "event":
                synth_trim = trim_audio(synth_file, start, end)
                bundle += [
                    amix_streams(
                        streams=[real_trim, synth_trim],
                        weights=weights,
                    )
                ]
            case "blank":
                bundle += [real_trim]

    synth_dur = int(
        (float(ffmpeg.probe(synth_file).get("format", {}).get("duration", None)) * 1000)
        // 1
    )
    # add on remainder to the end as if it's a blank
    if spans[-1][2] < synth_dur:
        bundle += [trim_audio(synth_file, spans[-1][2], synth_dur)]
    return ffmpeg.concat(*bundle, v=0, a=1)


async def keep_events(
    file: str | PathLike,
    spans: list[Span],
    output_dir: str | PathLike,
    mode: Literal["video", "audio", "both"],
) -> Path:
    """Slices out the events in spans, then concatenates them.

    Args:
        file: path to the video and/or audio file,
        spans: spans with events and blanks, only events will be cut out tho,
        output_dir: directory in which the output file will be generated


    Return:
        Path to the concatenated file.
    """
    pts = "PTS-STARTPTS"  # sets the starting point of each slice to 0
    extension = ".wav" if mode == "audio" else ".mp4"
    event_spans = [span for span in spans if span[0] == "event"]
    with TemporaryDirectory() as temp:
        bundle = []
        for _, start_ms, end_ms in event_spans:
            # i haven't slept in 24 hrs
            match mode:
                case "video":
                    trimmed = trim_video(file, start_ms, end_ms).setpts(pts)
                case "audio":
                    trimmed = trim_audio(file, start_ms, end_ms).filter_("asetpts", pts)
                case "both":
                    v_trim = trim_video(file, start_ms, end_ms).setpts(pts)
                    a_trim = trim_audio(file, start_ms, end_ms).filter_("asetpts", pts)
                    trimmed = ffmpeg.concat(v_trim, a_trim, v=1, a=1)
                case never:
                    assert_never(never)
            trimmed_clip = await write_streams(
                [trimmed],
                output_dir=temp,
                extension=extension,
            )
            bundle += [f"file '{trimmed_clip}'\n"]

        # caveman mode
        clip_list = str(new_file(temp)) + ".txt"

        with open(clip_list, "w", encoding="utf-8") as f:
            f.writelines(bundle)
        output_file = str(new_file(output_dir)) + extension
        system(f"ffmpeg -f concat -safe 0 -i {clip_list} {output_file}")

    return Path(output_file)


async def dub(
    video: str | PathLike, audio: str | PathLike, output_dir: str | PathLike
) -> Path:
    if not video:
        return Path(audio)

    streams = (ffmpeg.input(audio).audio, ffmpeg.input(video).video)

    video = Path(video)
    output_file = Path(f"{new_file(output_dir)}{video.suffix}")
    pipeline = ffmpeg.output(*streams, vcodec="copy", filename=output_file)

    await _run(pipeline)

    return output_file


async def cut(
    media_file: str | PathLike, start: str, finish: str, output_dir: str | PathLike
) -> Path:
    _input = ffmpeg.input(media_file, ss=start)
    media_file = Path(media_file)

    output_file = Path(f"{new_file(output_dir)}{media_file.suffix}")
    pipeline = ffmpeg.output(_input, to=finish, c="copy", filename=output_file)

    await _run(pipeline)

    return output_file


async def _run(pipeline):
    try:

        def _run_pipeline():
            pipeline.run(overwrite_output=True, capture_stderr=True)

        await concurrency.run_in_thread_pool(_run_pipeline)
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg Error stderr: {e.stderr}")
