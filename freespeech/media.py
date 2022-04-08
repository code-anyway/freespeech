import uuid
from tempfile import TemporaryDirectory
from typing import Dict, List, Tuple

import ffmpeg

from freespeech import storage
from freespeech.types import Audio, AudioEncoding, Video


def encoding_from_ffprobe(encoding: str) -> AudioEncoding:
    match encoding:
        case "opus":
            return "WEBM_OPUS"
        case "pcm_s16le":
            return "LINEAR16"
        case "aac":
            return "AAC"
        case invalid_encoding:
            raise ValueError(f"Invalid encoding: {invalid_encoding}")


def downmix_stereo_to_mono(audio: Audio, storage_url: str) -> Audio:
    new_audio = Audio(
        duration_ms=audio.duration_ms,
        storage_url=storage_url,
        suffix=audio.suffix,
        encoding=audio.encoding,
        sample_rate_hz=audio.sample_rate_hz,
        voice=audio.voice,
        lang=audio.lang,
        num_channels=1,
    )

    with TemporaryDirectory() as tmp_dir:
        assert audio.url is not None
        file = storage.get(audio.url, tmp_dir)
        stream = ffmpeg.input(filename=file).audio
        local_filename = f"{tmp_dir}/{new_audio._id}.{new_audio.suffix}"
        ffmpeg.output(
            stream,
            filename=local_filename,
            ac=1,  # audio channels = 1
        ).run(overwrite_output=True, capture_stderr=True)
        assert new_audio.url is not None
        storage.put(src_file=local_filename, dst_url=new_audio.url)

    return new_audio


def _parse_ffprobe_info(info: Dict, url: str) -> List[Audio | Video]:
    def parse_stream(stream: Dict) -> Audio | Video:
        match stream["codec_type"]:
            case "audio":
                return Audio(
                    duration_ms=int(float(info["format"]["duration"]) * 1000),
                    url=url,
                    storage_url="",
                    encoding=encoding_from_ffprobe(stream["codec_name"]),
                    sample_rate_hz=int(stream["sample_rate"]),
                    num_channels=stream["channels"],
                    suffix=url.split(".")[-1],
                )
            case "video":
                return Video(
                    duration_ms=int(float(info["format"]["duration"]) * 1000),
                    url=url,
                    storage_url="",
                    suffix=url.split(".")[-1],
                    # TODO (astaff): parse encoding properly
                    encoding="H264",
                )
            case codec_type:
                raise ValueError(f"Unsupported codec type: {codec_type}")

    return [parse_stream(s) for s in info["streams"]]


def probe(url: str) -> List[Audio | Video]:
    with TemporaryDirectory() as tmp_dir:
        local_file = storage.get(url, tmp_dir)
        info = ffmpeg.probe(local_file)
        return _parse_ffprobe_info(info, url)


def concat(clips: List[Tuple[int, Audio]], storage_url: str) -> Audio:
    with TemporaryDirectory() as tmp_dir:
        inputs = [
            (
                time_ms,
                ffmpeg.input(
                    filename=storage.get(audio.url, tmp_dir),
                ).audio,
            )
            for time_ms, audio in clips
            if audio.url is not None
        ]

        inputs = [
            audio.filter("adelay", delays=time_ms) if time_ms != 0 else audio
            for time_ms, audio in inputs
        ]

        # astaff (20220311): not specifying v and a gives a weird error
        # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
        stream = ffmpeg.concat(*inputs, v=0, a=1)
        (_, clip), *_ = clips
        output_file = f"{tmp_dir}/output.{clip.suffix}"

        ffmpeg.output(stream, output_file).run(
            overwrite_output=True, capture_stderr=True
        )

        (audio,) = probe(f"file://{output_file}")

        assert isinstance(audio, Audio)

        new_audio = Audio(
            duration_ms=audio.duration_ms,
            storage_url=storage_url,
            suffix=audio.suffix,
            encoding=audio.encoding,
            sample_rate_hz=audio.sample_rate_hz,
            voice=clip.voice,
            lang=clip.lang,
            num_channels=audio.num_channels,
        )
        assert new_audio.url is not None
        storage.put(output_file, new_audio.url)

        return new_audio


def mix(audio: List[Audio], weights: List[int], storage_url: str) -> Audio:
    *_, last_audio = audio

    with TemporaryDirectory() as tmp_dir:
        mixed_audio = ffmpeg.filter(
            [ffmpeg.input(storage.get(a.url, tmp_dir)).audio for a in audio],
            "amix",
            weights=" ".join([str(w) for w in weights]),
        )
        output_file = f"{tmp_dir}/output.{last_audio.suffix}"

        ffmpeg.output(mixed_audio, output_file).run(overwrite_output=True)

        (local_audio,) = probe(f"file://{output_file}")

        assert isinstance(local_audio, Audio)

        new_audio = Audio(
            duration_ms=local_audio.duration_ms,
            storage_url=storage_url,
            suffix=local_audio.suffix,
            encoding=local_audio.encoding,
            sample_rate_hz=local_audio.sample_rate_hz,
            voice=last_audio.voice,
            lang=last_audio.lang,
            num_channels=last_audio.num_channels,
        )
        assert new_audio.url is not None
        storage.put(output_file, new_audio.url)

    return new_audio


def add_audio(video: Video, audio: Audio, storage_url: str) -> Tuple[Video, Audio]:
    with TemporaryDirectory() as tmp_dir:
        audio_path = storage.get(audio.url, tmp_dir)
        video_path = storage.get(video.url, tmp_dir)

        file_name = f"{uuid.uuid4()}.{video.suffix}"
        output_path = f"{tmp_dir}/{file_name}"

        ffmpeg.output(
            ffmpeg.input(audio_path).audio, ffmpeg.input(video_path).video, output_path
        ).run(overwrite_output=True)

        output_url = f"{storage_url}{file_name}"
        storage.put(output_path, output_url)

        streams = probe(output_url)

        (output_audio,) = [s for s in streams if isinstance(s, Audio)]
        (output_video,) = [s for s in streams if isinstance(s, Video)]

        return (output_video, output_audio)
