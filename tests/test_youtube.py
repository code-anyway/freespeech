from freespeech import youtube
from freespeech.types import FileStorage


def test_download(tmp_path):
    url = "https://youtu.be/bhRaND9jiOA"

    youtube.download(url, FileStorage(path=tmp_path))
