import logging
import mimetypes
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import BinaryIO, Generator
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient
from google.api_core import exceptions as google_api_exceptions
from google.cloud import storage  # type: ignore

from freespeech import env
from freespeech.lib import concurrency
from freespeech.types import url

logger = logging.getLogger(__name__)


BLOCK_SIZE = 16 * 4096


@dataclass(frozen=False)
class GoogleStorageObject:
    bucket: str
    obj: str

    def __post_init__(self):
        if self.obj.startswith("/"):
            raise ValueError("object cannot start with `/`")


async def put(src: str | PathLike, dst: url) -> str:
    src_file = Path(src)
    dst_url = urlparse(dst)

    if not dst_url.path:
        ValueError(f"dst url is missing a path component: {dst}")

    match dst_url.scheme:
        case "file":

            def _copy():
                shutil.copy(src_file, dst_url.path)

            await concurrency.run_in_thread_pool(_copy)
            return dst_url.path
        case "gs":
            assert dst_url.path.startswith("/")
            dst_obj = GoogleStorageObject(dst_url.netloc, dst_url.path[1:])

            def _copy():
                _gs_copy_from_local(src_file, dst_obj)

            await concurrency.run_in_thread_pool(_copy)
            return f"gs://{dst_obj.bucket}/{dst_obj.obj}"
        case "az":
            blob_service_client: BlobServiceClient = (
                BlobServiceClient.from_connection_string(
                    env.get_azure_storage_connection_string()
                )
            )
            # TODO (astaff, 20220905): let's extract hardcoded stuff into variables
            # I am leaving this as is, because storage hierarchy (containers, blobs)
            # in Azure is a mess. On top of that access management is a world of pain.
            # I manually configured storage account (freespeech),
            # created a container (freespeech-files) with public read permissions.
            container_client = blob_service_client.get_container_client(
                "freespeech-files"
            )
            blob_name = dst_url.path[1:]
            with open(src, "rb") as data:
                container_client.upload_blob(name=blob_name, data=data)
            return (
                f"https://freespeech.blob.core.windows.net/freespeech-files/{blob_name}"
            )
        case scheme:
            raise ValueError(f"Unsupported url scheme ({scheme}) for {dst_url}.")


@contextmanager
def stream(src: url, mode: str) -> Generator[BinaryIO, None, None]:
    src_url = urlparse(src)
    with google_storage_client() as storage:
        bucket = storage.bucket(src_url.netloc)
        blob = bucket.blob(src_url.path[1:])
        try:
            yield blob.open(mode)
        finally:
            storage._http.close()


async def get(src: url, dst_dir: str | PathLike) -> str:
    src_url = urlparse(src)
    dst_dir = Path(dst_dir)

    if not dst_dir.is_dir():
        raise ValueError(f"dst_dir should be a directory: {dst_dir}")

    src_path = Path(src_url.path)
    dst_file = dst_dir / src_path.name

    match src_url.scheme:
        case "file":
            if src_path != dst_file:

                def _copy():
                    shutil.copy(src_url.path or "/", dst_file)

                await concurrency.run_in_thread_pool(_copy)
            return str(dst_file)
        case "gs":
            assert src_url.path.startswith("/")
            src_obj = GoogleStorageObject(src_url.netloc, src_url.path[1:])

            def _copy():
                return _gs_copy_from_gs(src_obj, dst_file)

            await concurrency.run_in_thread_pool(_copy)
            return str(dst_file)
        case scheme:
            raise ValueError(f"Unsupported url scheme ({scheme}) for {src_url}.")


def _gs_copy_from_local(src: Path, dst: GoogleStorageObject):
    try:
        with google_storage_client() as storage:
            bucket = storage.bucket(dst.bucket)
            blob = bucket.blob(dst.obj)
            mime_type, encoding = mimetypes.guess_type(src)
            blob.content_type = mime_type
            with open(str(src), "rb") as src_file:
                with blob.open("wb") as dst_file:
                    while bytes := src_file.read(BLOCK_SIZE):
                        dst_file.write(bytes)

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


def public_url(url: url) -> url:
    return url.replace("gs://", "https://storage.googleapis.com/")


def storage_url(url: url) -> url:
    return url.replace("https://storage.googleapis.com/", "gs://")
