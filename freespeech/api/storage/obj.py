import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from google.cloud import storage

logger = logging.getLogger(__name__)


@contextmanager
def google_storage_client():
    client = storage.Client()
    try:
        yield client
    finally:
        # Some Google client libraries are leaking resources
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        client._http.close()


def put(src_file: Path | str, dst_url: str):
    src_file = Path(src_file)

    url = urlparse(dst_url)

    match url.scheme:
        case "file":
            shutil.copy(src_file, url.path or "/")
        case "gs":
            with google_storage_client() as storage:
                bucket = storage.bucket(url.netloc)
                blob_file_name = url.path or "/"
                blob_file_name = blob_file_name[1:]  # omit leading /
                blob = bucket.blob(blob_file_name)
                blob.upload_from_filename(str(src_file))
        case scheme:
            raise ValueError(
                f"Unsupported url scheme ({scheme}) for {dst_url}.")


def get(src_url: str, dst_dir: Path | str) -> str:
    dst_dir = Path(dst_dir)

    url = urlparse(src_url)
    src_path = Path(url.path or "/")
    dst_file = dst_dir / src_path.name

    match url.scheme:
        case "file":
            if src_path != dst_file:
                shutil.copy(src_path, dst_file)
            return str(dst_file)
        case "gs":
            with google_storage_client() as storage:
                bucket = storage.bucket(url.netloc)
                blob = bucket.blob(str(src_path)[1:])  # omit leading /
                blob.download_to_filename(str(dst_file))
            return str(dst_file)
        case scheme:
            raise ValueError(
                f"Unsupported url scheme ({scheme}) for {src_url}.")
