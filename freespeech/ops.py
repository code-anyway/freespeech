import hashlib
import os
import tempfile
import re
from pathlib import Path
from typing import Dict, List

import ffmpeg
from google.cloud import texttospeech
from google.oauth2 import service_account
import googleapiclient.discovery

from pytube import YouTube


def hash(s: str) -> str:
    hashed = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return hashed


def extract_video_info(url: str) -> Dict[str, str]:
    yt = YouTube(url)

    return {
        "title": yt.title,
        "description": yt.description,
        "url": yt.watch_url,
    }


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


def text_to_speech(text: str, language_code: str, voice_name: str, speaking_rate: float, pitch: float, output_path: str):
    phrases = chunk(text, 1000)

    assert language_code in ("en-US", "ru-RU")
    assert voice_name in (
        *[f"en-US-Wavenet-{suffix}" for suffix in 'ABCDEFGHIJ'],
        *[f"ru-RU-Wavenet-{suffix}" for suffix in 'ABCDE']
    )

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

        # astaff (20220311): refactor to use in-memory stream instead of a disk file
        for i, response in enumerate(responses):
            file_name = str(Path(media_root) / f"{hash(text)}-{i}.wav")

            with open(file_name, "wb") as out:
                out.write(response.audio_content)

            inputs += [ffmpeg.input(file_name).audio]        

        # astaff (20220311): not specifying v and a gives a weird error
        # https://stackoverflow.com/questions/71390302/ffmpeg-python-stream-specifier-in-filtergraph-description-0concat-n-1s0-m
        stream = ffmpeg.concat(*inputs, v=0, a=1)
        
        ffmpeg.output(stream, output_path).run(overwrite_output=True, capture_stderr=True)



def download(url: str, root: Path):
    root = Path(root)
    yt = YouTube(url)
    audio = yt.streams.get_audio_only()
    video = yt.streams.get_highest_resolution()

    print(f"Video stream: {video}")
    print(f"Audio stream: {audio}")

    try:
        return (
            audio.download(output_path=root, filename=f"audio.webm"),
            video.download(output_path=root, filename=f"video.mp4", max_retries=10)
        )
    except Exception as e:
        raise RuntimeError(f"Unable to download {url}") from e

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

    ffmpeg.output(
        mixed_audio,
        video,
        output_path
    ).run(overwrite_output=True, capture_stderr=True)

    return output_path


def probe(path: Path) -> float:
    return ffmpeg.probe(path)


def read_paragraph_element(element):
    """Returns the text in the given ParagraphElement.

        Args:
            element: a ParagraphElement from a Google Doc.
    """
    text_run = element.get('textRun')
    if not text_run:
        return ''
    return text_run.get('content')


def read_structural_elements(elements):
    """Recurses through a list of Structural Elements to read a document's text where text may be
        in nested elements.

        Args:
            elements: a list of Structural Elements.
    """
    text = ''
    for value in elements:
        if 'paragraph' in value:
            elements = value.get('paragraph').get('elements')
            for elem in elements:
                text += read_paragraph_element(elem)
        elif 'table' in value:
            # The text in table cells are in nested Structural Elements and tables may be
            # nested.
            table = value.get('table')
            for row in table.get('tableRows'):
                cells = row.get('tableCells')
                for cell in cells:
                    text += read_structural_elements(cell.get('content'))
        elif 'tableOfContents' in value:
            # The text in the TOC is also in a Structural Element.
            toc = value.get('tableOfContents')
            text += read_structural_elements(toc.get('content'))
    return text


def extract_text_from_google_docs(url: str) -> str:
    """Returns text contents of Google Docs document specified in `url`"""
    SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
    SERVICE_ACCOUNT_FILE = os.environ['GOOGLE_APPLICATION_CREDENTIALS']

    document_id, *_ = re.findall(r"\/document\/d\/([a-zA-Z0-9-_]+)", url)

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = googleapiclient.discovery.build('docs', 'v1', credentials=credentials)

    document = service.documents().get(documentId=document_id).execute()
    return read_structural_elements(document.get('body').get('content'))