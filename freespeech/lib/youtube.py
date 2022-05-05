import html
import http.client
import json
import logging
import random
import time
import xml.etree.ElementTree as ET
from os import PathLike
from pathlib import Path
from typing import Dict, Sequence, Tuple

import httplib2
import pytube
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from freespeech.lib import media
from freespeech.types import Event, Language, Meta

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


def download_stream(
    stream: pytube.Stream, output_dir: str | PathLike, max_retries: int
) -> PathLike:
    file = Path(f"{media.new_file(output_dir)}.{stream.subtype}")
    stream.download(output_path=output_dir, filename=file.name, max_retries=max_retries)
    return Path(file)


def download(
    url: str, output_dir: str | PathLike, max_retries: int = 0
) -> Tuple[PathLike, PathLike, Meta, Dict[str, Sequence[Event]]]:
    """Downloads YouTube video from URL into output_dir.

    Args:
        url: Video URL (i.e. "https://youtu.be/bhRaND9jiOA")
        output_dir: directory where video and audio files will be created.

    Returns:
        A tuple (audio_stream, video_stream, info).
    """
    yt = pytube.YouTube(url)

    filtered = yt.streams.filter(only_audio=True, audio_codec="opus")
    *_, audio = filtered.order_by("abr")

    video = yt.streams.get_highest_resolution()
    video_streams = list(yt.streams.filter(resolution="720p", mime_type="video/mp4"))

    if not video_streams:
        video_streams = list(
            yt.streams.filter(resolution="360p", mime_type="video/mp4")
        )
        logger.warning(f"No 720p strams available for {url}")
        logger.warning(f"360p streams available: {video_streams}")

    logger.info(f"Downloading {audio} and {video}")

    audio_stream = download_stream(
        stream=audio, output_dir=output_dir, max_retries=max_retries
    )

    video_stream = None
    for stream in video_streams:
        try:
            video_stream = download_stream(
                stream=stream, output_dir=output_dir, max_retries=max_retries
            )
        except http.client.IncompleteRead as e:
            # Some streams won't download.
            logger.warning(f"Incomplete read for stream {stream} of {url}: {str(e)}")
        except KeyError as e:
            # Some have content-length missing.
            logger.warning(f"Missing key for {stream} of {url}: {str(e)}")

    if not video_stream:
        raise RuntimeError(
            f"Unable to download video stream for {url}. Candidates: {video_streams}"
        )

    info = Meta(title=yt.title, description=yt.description, tags=yt.keywords)
    captions = [(caption.code, caption.xml_captions) for caption in yt.captions]

    return audio_stream, video_stream, info, convert_captions(captions)


def get_captions(url: str, lang: Language) -> Sequence[Event]:
    yt = pytube.YouTube(url)
    captions = dict((caption.code, caption.xml_captions) for caption in yt.captions)
    if lang not in captions:
        raise ValueError(f"{url} has no captions for {lang}")
    return captions[lang]


def _language_tag(lang: str) -> str | None:
    match lang:
        case "en" | "en-US":
            return "en-US"
        case "uk":
            return "uk-UA"
        case "ru":
            return "ru-RU"
        case "pt":
            return "pt-PT"
        case "de":
            return "de-DE"
        case unsupported_language:
            logger.warning(f"Unsupported caption language: {unsupported_language}")
            return None


def parse(xml: str) -> Sequence[Event]:
    """Parses YouTube XML captions and generates a sequence of speech Events."""

    body = ET.fromstring(xml).find("body")
    assert body is not None

    return [
        Event(
            time_ms=int(child.attrib["t"]),
            duration_ms=int(child.attrib["d"]),
            chunks=[html.unescape(child.text)],
        )
        for child in body
        if child.text
    ]


def convert_captions(captions: Sequence[Tuple[str, str]]) -> Dict[str, Sequence[Event]]:
    """Converts YouTube captions for each language into speech Events."""
    return {
        language_tag: parse(xml_captions)
        for code, xml_captions in captions
        if (language_tag := _language_tag(code))
    }
