import logging
import shutil
from pathlib import Path
from urllib.parse import ParseResult, urlparse

from google.cloud import storage

logger = logging.getLogger(__name__)


def put(src_file: Path | str, dst_url: str):
    logger.debug(f"put: src_file={src_file} dst_url={dst_url}")

    if isinstance(src_file, str):
        src_file = Path(src_file)

    match urlparse(dst_url):
        case ParseResult(scheme="file") as url:
            shutil.copy(src_file, url.path or "/")
        case ParseResult(scheme="gs") as url:
            storage_client = storage.Client()
            try:
                bucket = storage_client.bucket(url.netloc)
                blob_file_name = url.path or "/"
                blob_file_name = blob_file_name[1:]  # omit leading /
                blob = bucket.blob(blob_file_name)
                blob.upload_from_filename(str(src_file))
            finally:
                # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
                storage_client._http.close()
        case ParseResult() as url:
            raise ValueError(f"Unsupported url scheme ({url.scheme}) for {dst_url}.")


def get(src_url: str, dst_dir: Path | str):
    if isinstance(dst_dir, str):
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
            storage_client = storage.Client()
            try:
                bucket = storage_client.bucket(url.netloc)
                blob = bucket.blob(str(src_path)[1:])  # omit leading /
                blob.download_to_filename(str(dst_file))
            finally:
                # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
                storage_client._http.close()
            return str(dst_file)
        case scheme:
            raise ValueError(f"Unsupported url scheme ({scheme}) for {src_url}.")
