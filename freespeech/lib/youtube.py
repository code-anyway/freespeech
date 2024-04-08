import asyncio
import http.client
import json
import logging
import random
import re
import time
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence
from uuid import uuid4

import gdown
import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from yt_dlp import YoutubeDL

from freespeech.lib import transcript
from freespeech.types import Event, Language, Meta, platform

logger = logging.getLogger(__name__)

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    http.client.NotConnected,
    http.client.IncompleteRead,
    http.client.ImproperConnectionState,
    http.client.CannotSendRequest,
    http.client.CannotSendHeader,
    http.client.ResponseNotReady,
    http.client.BadStatusLine,
)


YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def initialize_upload(
    youtube, video_file, title, description, tags, category_id, privacy_status
):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        # The chunksize parameter specifies the size of each chunk of data, in
        # bytes, that will be uploaded at a time. Set a higher value for
        # reliable connections as fewer chunks lead to faster uploads.
        # Set a lower value for better recovery on less reliable connections.
        #
        # Setting "chunksize" equal to -1 in the code below means that
        # the entire file will be uploaded in a single HTTP request.
        # (If the upload fails, it will still be retried where it left off.)
        media_body=MediaFileUpload(video_file, chunksize=-1, resumable=True),
    )

    resumable_upload(insert_request)


def resumable_upload(insert_request):
    """
    This method implements an exponential backoff strategy
    to resume a failed upload.
    """
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            logger.info("Uploading file...")
            status, response = insert_request.next_chunk()
            logger.info(f"Status: {status}")
            if response is not None:
                if "id" in response:
                    logger.info(
                        f"Video id '{ response['id']}' was successfully" " uploaded."
                    )
                else:
                    exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = (
                    "A retriable HTTP error" f" {e.resp.status} occurred:\n{e.content}"
                )
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            logger.error(error)
            retry += 1
            if retry > MAX_RETRIES:
                logger.info("No longer attempting to retry.")
                return

            max_sleep = 2**retry
            sleep_seconds = random.random() * max_sleep
            logger.info("Sleeping {sleep_seconds} seconds and then retrying...")
            time.sleep(sleep_seconds)


def upload(video_file, meta_file, credentials_file):
    credentials = Credentials.from_authorized_user_file(credentials_file)

    youtube = build(
        YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials
    )

    with open(meta_file) as fd:
        meta = json.load(fd)

    DISCLAIMER = (
        "The voice in this video has been automatically generated based on"
        f" translated transcript of the original video {meta['url']}."
    )
    description = meta["description"] + "\n\n" + DISCLAIMER

    initialize_upload(
        youtube,
        video_file=video_file,
        title=meta["title"],
        description=description,
        tags=meta.get("tags") or [],
        category_id=meta.get("category_id") or "22",
        privacy_status="unlisted",
    )


async def download(
    url: str,
    output_dir: str | PathLike,
    max_retries: int = 0,
) -> tuple[Path, Path | None]:
    # Download and merge the best video-only format and the best audio-only format,
    # or download the best combined format if video-only format is not available.
    # more here: https://github.com/yt-dlp/yt-dlp#format-selection-examples

    audio, video = None, None
    match platform(url):
        case "Google Drive":
            audio = await _download_from_gdrive(url, output_dir)
            video = await _download_from_gdrive(url, output_dir)
        case "Twitter":
            audio = await _download_media(url, output_dir, pipeline="b")
            video = await _download_media(url, output_dir, pipeline="b")
        case _:
            audio = await _download_media(url, output_dir, pipeline="ba")
            video = await _download_media(url, output_dir, pipeline="bv[ext=mp4]")

    return audio, video


async def _download_from_gdrive(url: str, output_dir: str | PathLike) -> Path:
    output_path = Path(output_dir) / f"{uuid4()}.gdrive"
    gdown.download(url, str(output_path), fuzzy=True, quiet=False)
    return output_path


async def _download_media(url: str, output_dir: str | PathLike, pipeline: str) -> Path:
    """
    Download the media using the given pipeline.
    """
    output_prefix = str(Path(output_dir) / f"{uuid4()}")
    command = f"""yt-dlp \
        -f \"{pipeline}\" \
        -o \"{output_prefix}.%(ext)s\" \
        --external-downloader aria2c \
        --external-downloader-args '-c -j 3 -x 3 -s 3 -k 1M' \
        {url}"""

    stdout = await run(command)

    # extract path from the result
    res = re.search(r"Destination: (.*)", stdout, flags=re.M)
    if res is None:
        raise RuntimeError(f"Could find output file in stdout: {stdout}")

    output = Path(res.group(1))
    return output


async def run(command: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed with code {proc.returncode}: {stderr!r}")

    logger.debug(f"yt-dlp output: {stdout!r}")

    return stdout.decode()


async def get_meta(url: str) -> Meta:
    command = f"""yt-dlp --dump-json {url}"""
    stdout = await run(command)
    meta = json.loads(stdout)

    return Meta(
        title=meta["title"],
        description=meta["description"],
        tags=meta["tags"],
        duration_ms=int(meta["duration"]) * 1000,
    )


def parse_captions(srt: str) -> Sequence[Event]:
    return transcript.vtt_to_events(srt)


async def get_captions(url: str, lang: Language) -> Sequence[Event]:
    try:
        captions = await _get_captions(url, lang)
    except (ValueError, FileNotFoundError):
        # try short language code
        short_lang = str(lang)[:2]
        try:
            logger.warning(
                f"{url} doesn't have captions for {lang}, trying {short_lang}"
            )  # noqa: E501
            captions = await _get_captions(url, short_lang)
        except (ValueError, FileNotFoundError):
            raise RuntimeError(
                f"Could not find captions for {lang} or {short_lang} in {url}"
            )
    return captions


async def _get_captions(url: str, lang: str):
    with TemporaryDirectory() as tmpdir:
        output = f"{tmpdir}/subtitles"
        with YoutubeDL(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [lang],
                "subtitlesformat": "vtt",
                "outtmpl": output,
                "skip_download": True,
            }
        ) as ydl:
            ydl.download([url])
            with open(f"{output}.{lang}.vtt") as fd:
                return list(parse_captions(fd.read()))
