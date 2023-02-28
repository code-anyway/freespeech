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
from uuid import uuid4

import httplib2
import pytube
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from freespeech.lib import concurrency
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


def download(
    url: str,
    output_dir: str | PathLike,
    max_retries: int = 0,
) -> tuple[Path, Path | None]:
    """Downloads YouTube video from URL into output_dir.

    Args:
        url: Video URL (i.e. "https://youtu.be/bhRaND9jiOA")
        output_dir: directory where video and audio files will be created.

    Returns:
        Audio and video files.
    """
    yt = pytube.YouTube(url)
    filtered = yt.streams.filter(only_audio=True)
    *_, audio = filtered.order_by("abr")
    audio_file = audio.download(
        output_path=output_dir,
        filename=f"{uuid4()}.{audio.subtype}",
        max_retries=max_retries,
    )

    video_streams = []
    for resolution in ("1080p", "720p", "360p"):
        video_streams = list(
            yt.streams.filter(resolution=resolution, mime_type="video/mp4")
        )
        if video_streams:
            break
        else:
            logger.warning(f"Resolution {resolution} is not available for {url}")

    video_file = None
    for stream in video_streams:
        try:
            video_file = stream.download(
                output_path=output_dir,
                filename=f"{uuid4()}.{stream.subtype}",
                max_retries=max_retries,
            )
            break
        except http.client.IncompleteRead as e:
            # Some streams won't download.
            logger.warning(f"Incomplete read for stream {stream} of {url}: {str(e)}")
        except KeyError as e:
            # Some have content-length missing.
            logger.warning(f"Missing key for {stream} of {url}: {str(e)}")

    if video_file is None:
        raise RuntimeError(
            f"Unable to download video stream for {url}. Candidates: {video_streams}"
        )

    return Path(audio_file), Path(video_file)


async def download_async(
    url: str,
    output_dir: str | PathLike,
    max_retries: int = 0,
) -> tuple[Path, Path | None]:
    return await concurrency.run_in_thread_pool(download, url, output_dir, max_retries)


def get_meta(url: str) -> Meta:
    yt = pytube.YouTube(url)
    duration_ms = yt.length * 1000
    return Meta(
        title=yt.title,
        description=yt.description,
        tags=yt.keywords,
        duration_ms=duration_ms,
    )


def get_captions(url: str, lang: Language) -> Sequence[Event]:
    yt = pytube.YouTube(url)
    xml_captions = [(caption.code, caption.xml_captions) for caption in yt.captions]

    captions = convert_captions(xml_captions)
    if lang not in captions:
        raise ValueError(f"{url} has no captions for {lang}")

    return captions[lang]


def _language_tag(lang: str) -> str | None:
    match lang:
        case "en" | "en-US" | "a.en" | "en-GB":
            return "en-US"
        case "uk":
            return "uk-UA"
        case "ru" | "a.ru":
            return "ru-RU"
        case "pt":
            return "pt-PT"
        case "de":
            return "de-DE"
        case "es":
            return "es-US"
        case "fr":
            return "fr-FR"
        case unsupported_language:
            logger.warning(f"Unsupported caption language: {unsupported_language}")
            return None


def parse(xml: str) -> Sequence[Event]:
    """Parses YouTube XML captions and generates a sequence of speech Events."""

    def _extract_text(element):
        inner = "".join([s.text for s in element.findall("s") or []])
        return inner or element.text or ""

    body = ET.fromstring(xml).find("body")
    assert body is not None

    raw_events = [
        (
            int(child.attrib["t"]),
            int(duration)
            if (duration := child.attrib.get("d", None)) is not None
            else None,
            [html.unescape(_extract_text(child))],
        )
        for child in body.findall("p") or []
    ]

    return [
        Event(
            time_ms=time_ms,
            duration_ms=duration_ms
            if duration_ms is not None
            else next_time_ms - time_ms,
            chunks=chunks,
        )
        for (time_ms, duration_ms, chunks), (next_time_ms, _, _) in zip(
            raw_events, raw_events[1:] + [(0, None, [])]
        )
    ]


def convert_captions(captions: Sequence[Tuple[str, str]]) -> Dict[str, Sequence[Event]]:
    """Converts YouTube captions for each language into speech Events."""

    auto_captions = [(lang, xml) for lang, xml in captions if lang.startswith("a.")]
    normal_captions = [
        (lang, xml) for lang, xml in captions if not lang.startswith("a.")
    ]

    return {
        language_tag: parse(xml_captions)
        for code, xml_captions in auto_captions + normal_captions
        if (language_tag := _language_tag(code))
    }
