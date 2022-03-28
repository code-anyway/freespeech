import http.client
import json
import random
import time
from typing import BinaryIO, Callable, Any, Generator, Dict
from pathlib import Path
from pytube import YouTube
from contextlib import contextmanager
from tempfile import TemporaryDirectory


import google_auth_oauthlib.flow
import httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


from freespeech.types import Storage, FileStorage, GoogleStorage, Audio, Video

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


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


# Reference resources:
# - https://github.com/tokland/youtube-upload/blob/master/youtube_upload/auth/__init__.py  # noqa: 501
# - https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps#python  # noqa: 501
# - https://google-auth-oauthlib.readthedocs.io/en/latest/reference/google_auth_oauthlib.flow.html  # noqa: 501
def authorize(secret_file, credentials_file):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        secret_file,
        scopes=YOUTUBE_SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, _ = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission.
        # ecommended for web server apps.
        access_type="offline",
        prompt="consent",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )

    print(f"Please go to this URL: {authorization_url}")

    # The user will get an authorization code. This code is used to get the
    # access token.
    code = input("Enter the authorization code: ")
    flow.fetch_token(code=code)

    with open(credentials_file, "w") as fd:
        fd.write(flow.credentials.to_json())


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

    google_auth_oauthlib

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


def extract_video_info(url: str) -> Dict[str, str]:
    yt = YouTube(url)

    return {
        "title": yt.title,
        "description": yt.description,
        "url": yt.watch_url,
        "tags": yt.keywords,
    }


@contextmanager
def get_on_progress_callback(
    storage: Storage,
    file_name: str
) -> Generator[Callable[[Any, bytes, int], None], None, None]:
    match storage:
        case FileStorage((path)):
            with open(path / file_name, "wb") as fd:
                try:
                    def _local_storage_callback(
                        chunk: bytes,
                        file_handler: bytes,
                        bytes_remaining: int
                    ) -> None:
                        fd.write(file_handler)
                    yield _local_storage_callback
                finally:
                    pass
        case GoogleStorage():
            raise NotImplementedError(
                "Google Cloud storage is not yet implemented.")


def download(url: str, storage: Storage) -> Tuple[Audio, Video]:
    yt = YouTube(url)

    Audio(
        
    )

    audio = yt.streams.get_audio_only()
    video = yt.streams.get_highest_resolution()

    with TemporaryDirectory() as output:
        try:
            with get_on_progress_callback(storage, "audio.webm") \
                 as on_progress_callback:
                yt.register_on_progress_callback(on_progress_callback)
                audio.download(output_path=output, filename="audio.webm")

            with get_on_progress_callback(storage, "video.mp4") \
                 as on_progress_callback:
                yt.register_on_progress_callback(on_progress_callback)
                video.download(output_path=output, filename="video.mp4"),
        except Exception as e:
            raise RuntimeError(f"Unable to download {url}") from e
