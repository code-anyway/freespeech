import hashlib


from freespeech import youtube, env, storage


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
GS_TEST_BUCKET = "freespeech-tests"
VIDEO_URL = "https://youtu.be/bhRaND9jiOA"


def get_hash(filename):
    sha256_hash = hashlib.sha256()

    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def test_download_local(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FREESPEECH_STORAGE_URL",
        f"file://{tmp_path}")

    media = youtube.download(VIDEO_URL, env.get_storage_url())

    assert media.title == "Announcer's test"
    assert media.description == VIDEO_DESCRIPTION
    assert media.tags == ["announcer's", 'test']
    assert media.origin == VIDEO_URL

    audio, = media.audio
    video, = media.video

    assert audio.url == f"file://{tmp_path}/{audio._id}.webm"
    assert audio.duration_ms == 29_000

    assert video.url == f"file://{tmp_path}/{video._id}.mp4"
    assert video.duration_ms == 29_000

    filename = storage.get(audio.url, tmp_path)
    assert get_hash(filename) == \
        "7b0dfb36784281f06c09011d631289f34aed8ba1cf0411b49d60c1d2594f7fe9"
    filename = storage.get(video.url, tmp_path)
    assert get_hash(filename) == \
        "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"


def test_download_google_storage(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FREESPEECH_STORAGE_URL",
        f"gs://{GS_TEST_BUCKET}/streams/")

    media = youtube.download(VIDEO_URL, env.get_storage_url())

    assert media.title == "Announcer's test"
    assert media.description == VIDEO_DESCRIPTION
    assert media.tags == ["announcer's", 'test']
    assert media.origin == VIDEO_URL

    audio, = media.audio
    video, = media.video

    assert audio.url == f"gs://{GS_TEST_BUCKET}/streams/{audio._id}.webm"
    assert audio.duration_ms == 29_000

    assert video.url == f"gs://{GS_TEST_BUCKET}/streams/{video._id}.mp4"
    assert video.duration_ms == 29_000

    filename = storage.get(audio.url, tmp_path)
    assert get_hash(filename) == \
        "7b0dfb36784281f06c09011d631289f34aed8ba1cf0411b49d60c1d2594f7fe9"
    filename = storage.get(video.url, tmp_path)
    assert get_hash(filename) == \
        "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"
