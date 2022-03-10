#!/usr/bin/env python3


import clip
import sys
import tempfile

from pathlib import Path


"""Synthesizes speech from the input string of text or ssml.
Make sure to be working in a virtual environment.

Note: ssml must be well-formed according to:
    https://www.w3.org/TR/speech-synthesis/
"""
from google.cloud import texttospeech
import split_text


def text_to_speech(file_name: str, language_code: str, voice_name: str, speaking_rate: float):
    with open(file_name) as lines:
        phrases = split_text.chunk("\n".join(list(lines)), 1000)

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
                pitch=-4.0,
                speaking_rate=speaking_rate
            )
        )
        for phrase in phrases
    ]

    return [response.audio_content for response in responses]


if __name__ == '__main__':
    _, url, voiceover_path, output_path, speaking_rate = sys.argv  
    speaking_rate = float(speaking_rate)

    with tempfile.TemporaryDirectory() as media_root:
        voiceover_name = Path(voiceover_path).stem
        voiceover_suffix = Path(voiceover_path).suffix

        if voiceover_suffix == ".wav":
            audio, video = clip.download(url, root=media_root)
            res = clip.add_audio(
                video_path=video,
                audio_paths=[audio, voiceover_path],
                output_path=str(Path(output_path) / f"{clip.hash(url)}-{voiceover_name}.mp4"),
                weights=[5, 10])
        elif voiceover_suffix == ".txt":
            if voiceover_name == "ru":
                speech = text_to_speech(voiceover_path, "ru-RU", "ru-RU-Wavenet-D", speaking_rate)
            if voiceover_name == "en":
                speech = text_to_speech(voiceover_path, "en-EN", "en-US-Wavenet-I", speaking_rate)
            
            files = []
            for i, chunk in enumerate(speech):
                file_name = str(Path(output_path).resolve() / f"{clip.hash(url)}-{voiceover_name}-{i}.wav")
                files += [file_name]

                with open(file_name, "wb") as out:
                    out.write(chunk)
            
            with open(Path(output_path) / f"{clip.hash(url)}-{voiceover_name}.list", "w") as f:
                for line in files:
                    f.write(f"file '{line}'\n")
        else:
            raise NotImplementedError(f"Unsupported voiceover extension: {voiceover_suffix}")

