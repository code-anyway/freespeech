import shutil

from pathlib import Path

from urllib.parse import ParseResult, urlparse

from google.cloud import storage


def put(src_path: Path, dst_url: str):
    match urlparse(dst_url):
        case ParseResult(scheme="file") as url:
            shutil.copy(src_path, url.path)
        case ParseResult(scheme="gs") as url:
            storage_client = storage.Client()
            bucket = storage_client.bucket(url.netloc)
            blob = bucket.blob(url.path[1:])  # omit leading /
            blob.upload_from_filename(str(src_path))
        case ParseResult() as url:
            raise ValueError(
                f"Unsupported url scheme ({url.scheme}) for {dst_url}.")


def get(src_url: str, dst_path: Path):
    match urlparse(src_url):
        case ParseResult(scheme="file") as url:
            src_path = Path(url.path)
            shutil.copy(src_path, dst_path / src_path.name)
        case ParseResult(scheme="gs") as url:
            src_path = Path(url.path)
            storage_client = storage.Client()
            bucket = storage_client.bucket(url.netloc)
            blob = bucket.blob(str(src_path)[1:])  # omit leading /
            blob.download_to_filename(str(dst_path / src_path.name))
        case ParseResult() as url:
            raise ValueError(
                f"Unsupported url scheme ({url.scheme}) for {src_url}.")
