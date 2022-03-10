import hashlib
from pathlib import Path
from typing import List

import ffmpeg
from pytube import YouTube


def hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def download(url: str, root: Path):
    root = Path(root)
    yt = YouTube(url)
    audio, = yt.streams.filter(mime_type="audio/webm", abr="160kbps")
    video, = yt.streams.filter(mime_type="video/mp4", res="1080p")

    return (
        audio.download(output_path=root, filename=f"{hash(url)}.webm"),
        video.download(output_path=root, filename=f"{hash(url)}.mp4")
    )


def add_audio(video_path: str, audio_paths: List[str], output_path: str, weights: List[int]):
    video_duration = float(ffmpeg.probe(video_path)['format']['duration'])
    audio_durations = [
        float(ffmpeg.probe(path)['format']['duration'])
        for path in audio_paths
    ]

    assert all(abs(d - video_duration) < 1.0 for d in audio_durations)

    video = ffmpeg.input(video_path).video    
    mixed_audio = ffmpeg.filter(
        [
            ffmpeg.input(audio_path).audio
            for audio_path in audio_paths
        ],
        "amix",
        weights=' '.join([str(w) for w in weights])
    )

    return ffmpeg.output(
        mixed_audio,
        video,
        output_path
    ).run(overwrite_output=True)

