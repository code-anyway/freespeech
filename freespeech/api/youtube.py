import http.client
import json
import logging
import random
import time

import httplib2
import pytube
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from freespeech.lib import media
from freespeech.types import Info
from typing import Tuple
from pathlib import Path


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
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            print(f"Status: {status}")
            if response is not None:
                if "id" in response:
                    print(f"Video id '{ response['id']}' was successfully" " uploaded.")
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
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                print("No longer attempting to retry.")
                return

            max_sleep = 2**retry
            sleep_seconds = random.random() * max_sleep
            print("Sleeping {sleep_seconds} seconds and then retrying...")
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


def download_stream(stream: pytube.Stream, output_dir: media.path) -> Path:
    file = media.new_file(output_dir)
    stream.download(output_path=output_dir, filename=file.name)
    return Path(file)


def download(url: str, output_dir: media.path) -> Tuple[Path, Path, Info]:
    yt = pytube.YouTube(url)

    filtered = yt.streams.filter(only_audio=True, audio_codec="opus")
    audio, *_ = filtered.order_by("abr")
    video = yt.streams.get_highest_resolution()

    logger.info(f"Downloading {audio} and {video}")

    audio_stream = download_stream(stream=audio, output_dir=output_dir)
    video_stream = download_stream(stream=video, output_dir=output_dir)

    info = Info(title=yt.title, description=yt.description, tags=yt.keywords)

    return audio_stream, video_stream, info