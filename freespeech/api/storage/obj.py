import logging
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from google.api_core import exceptions as google_api_exceptions
from google.cloud import storage

from freespeech.types import path, url

logger = logging.getLogger(__name__)


@dataclass(frozen=False)
class GoogleStorageObject:
    bucket: str
    obj: str

    def __post_init__(self):
        if self.obj.startswith("/"):
            raise ValueError("object cannot start with `/`")


def put(src: path, dst: url) -> str:
    src_file = Path(src)
    dst_url = urlparse(dst)

    if not dst_url.path:
        ValueError(f"dst url is missing a path component: {dst}")

    match dst_url.scheme:
        case "file":
            shutil.copy(src_file, dst_url.path)
            return dst_url.path
        case "gs":
            assert dst_url.path.startswith("/")
            dst_obj = GoogleStorageObject(dst_url.netloc, dst_url.path[1:])
            _gs_copy_from_local(src_file, dst_obj)
            return f"gs://{dst_obj.bucket}/{dst_obj.obj}"
        case scheme:
            raise ValueError(f"Unsupported url scheme ({scheme}) for {dst_url}.")


def get(src: url, dst_dir: path) -> str:
    src_url = urlparse(src)
    dst_dir = Path(dst_dir)

    if not dst_dir.is_dir():
        raise ValueError(f"dst_dir should be a directory: {dst_dir}")

    src_path = Path(src_url.path)
    dst_file = dst_dir / src_path.name

    match src_url.scheme:
        case "file":
            if src_path != dst_file:
                shutil.copy(src_url.path or "/", dst_file)
            return str(dst_file)
        case "gs":
            assert src_url.path.startswith("/")
            src_obj = GoogleStorageObject(src_url.netloc, src_url.path[1:])
            _gs_copy_from_gs(src_obj, dst_file)
            return str(dst_file)
        case scheme:
            raise ValueError(f"Unsupported url scheme ({scheme}) for {src_url}.")


def _gs_copy_from_local(src: Path, dst: GoogleStorageObject):
    try:
        with google_storage_client() as storage:
            bucket = storage.bucket(dst.bucket)
            blob = bucket.blob(dst.obj)
            blob.upload_from_filename(src)
    except google_api_exceptions.GoogleAPICallError as e:
        extra = {
            "details": e.details,
            "response": e.response,
        }
        logger.error(f"API Call Error while copying to {dst}: {e.message}", extra=extra)
        raise e


def _gs_copy_from_gs(src: GoogleStorageObject, dst: Path):
    try:
        with google_storage_client() as storage:
            bucket = storage.bucket(src.bucket)
            blob = bucket.blob(src.obj)
            blob.download_to_filename(dst)
        return str(dst)
    except google_api_exceptions.GoogleAPICallError as e:
        extra = {
            "details": e.details,
            "response": e.response,
        }
        logger.error(
            f"API Call Error while copying from {src}: {e.message}", extra=extra
        )
        raise e


@contextmanager
def google_storage_client():
    client = storage.Client()
    try:
        yield client
    finally:
        # Some Google client libraries are leaking resources
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        client._http.close()
