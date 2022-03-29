import hashlib
from urllib.parse import urlparse, ParseResult


from freespeech import youtube, env


VIDEO_DESCRIPTION = (
    "One hen\n\n"
    "Two ducks\n\n"
    "Three squawking geese\n\n"
    "Four limerick oysters\n\n"
    "Five corpulent porpoises\n\n"
    "Six pairs of Don Alverzo's tweezers\n\n"
    "Seven thousand Macedonians in full battle array\n\n"
    "Eight brass monkeys from the ancient sacred crypts of Egypt\n\n"
    "Nine apathetic, sympathetic, diabetic old men on roller skates, "
    "with a marked propensity towards procrastination and sloth"""
)


def check_hash(url, expected):
    sha256_hash = hashlib.sha256()

    match urlparse(url):
        case ParseResult(scheme="file") as url:
            filename = url.path
        case ParseResult(scheme="gs") as url:
            storage_client = storage.Client()
            bucket = storage_client.bucket(url.netloc)

            # Construct a client side representation of a blob.
            # Note `Bucket.blob` differs from `Bucket.get_blob` as it doesn't retrieve
            # any content from Google Cloud Storage. As we don't need additional data,
            # using `Bucket.blob` is preferred here.
            blob = bucket.blob(source_blob_name)
            blob.download_to_filename(destination_file_name)            
            with open(filename,"rb") as f:
                # Read and update hash string value in blocks of 4K
                for byte_block in iter(lambda: f.read(4096),b""):
                    sha256_hash.update(byte_block)
                print(sha256_hash.hexdigest())


def test_download_local(tmp_path, monkeypatch):
    monkeypatch.setenv("FREESPEECH_STORAGE_URL", f"file://{tmp_path}")

    url = "https://youtu.be/bhRaND9jiOA"
    media = youtube.download(url, env.get_storage_url())

    assert media.title == "Announcer's test"
    assert media.description == VIDEO_DESCRIPTION
    assert media.tags == ["announcer's", 'test']
    assert media.origin == url

    audio, = media.audio
    video, = media.video

    assert audio.url == f"file://{tmp_path}/{audio._id}.mp4"
    assert audio.duration_ms == 29_000

    assert video.url == f"file://{tmp_path}/{video._id}.mp4"
    assert video.duration_ms == 29_000


def test_download_google_storage(monkeypatch):
    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "gs://freespeech-test/streams/")

    url = "https://youtu.be/bhRaND9jiOA"
    media = youtube.download(url, env.get_storage_url())

    assert media.title == "Announcer's test"
    assert media.description == VIDEO_DESCRIPTION
    assert media.tags == ["announcer's", 'test']
    assert media.origin == url

    audio, = media.audio
    video, = media.video

    assert audio.url == f"file://{tmp_path}/{audio._id}.mp4"
    assert audio.duration_ms == 29_000

    assert video.url == f"file://{tmp_path}/{video._id}.mp4"
    assert video.duration_ms == 29_000
