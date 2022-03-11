import hashlib
import tempfile
import re
from pathlib import Path
from typing import List

import ffmpeg
import freespeech.split_text as split_text
from google.cloud import texttospeech
from pytube import YouTube


def hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def chunk(text: str, max_chars: int) -> List[str]:
    # If capturing parentheses are used in pattern,
    # then the text of all groups in the pattern
    # are also returned as part of the resulting list.
    sentences = re.split(r"(\!|\?|\.)", text)
    def chunk_sentences():
        res = ""
        for s in sentences:
            if len(res) + len(s) > max_chars:
                yield res
                res = s
            else:
                res += s
        if res:
            yield res

    return list(chunk_sentences())


def text_to_speech(file_name: str, language_code: str, voice_name: str, speaking_rate: float, pitch: float, output_path: str):
    with open(file_name) as lines:
        phrases = chunk("\n".join(list(lines)), 1000)

    client = texttospeech.TextToSpeechClient()

    responses = [
        client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=phrase),
            voice=texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                pitch=pitch,
                speaking_rate=speaking_rate
            )
        )
        for phrase in phrases
    ]

    with tempfile.TemporaryDirectory() as media_root:
        inputs = []

        # astaff (20220311): refactor to use in-memory stream instead of disk file
        for i, response in enumerate(responses):
            file_name = str(Path(media_root) / f"{hash(file_name)}-{i}.wav")

            with open(file_name, "wb") as out:
                out.write(response.audio_content)

            inputs += [ffmpeg.input(file_name).audio]        

        # astaff (20220311): not specifying v and a gives a weird error
        # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
        stream = ffmpeg.concat(*inputs, v=0, a=1)
        
        ffmpeg.output(stream, output_path).run(overwrite_output=True)



def download(url: str, root: Path):
    root = Path(root)
    yt = YouTube(url)
    audio, = yt.streams.filter(mime_type="audio/webm", abr="160kbps")
    video, = yt.streams.filter(mime_type="video/mp4", res="1080p")

    return (
        audio.download(output_path=root, filename=f"audio.webm"),
        video.download(output_path=root, filename=f"video.mp4")
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


def probe(path: Path) -> float:
    return ffmpeg.probe(path)

