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

    filename = storage.get(audio.url, tmp_path)
    assert get_hash(filename) == \
        "0163fb2ee8772de9371c2cab6bc1f00c4063a2758ebef48a9a2bed510fc533d6"
    filename = storage.get(video.url, tmp_path)
    assert get_hash(filename) == \
        "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"


def test_download_google_storage(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FREESPEECH_STORAGE_URL",
        f"gs://{GS_TEST_BUCKET}/streams/")

    url = "https://youtu.be/bhRaND9jiOA"
    media = youtube.download(url, env.get_storage_url())

    assert media.title == "Announcer's test"
    assert media.description == VIDEO_DESCRIPTION
    assert media.tags == ["announcer's", 'test']
    assert media.origin == url

    audio, = media.audio
    video, = media.video

    assert audio.url == f"gs://{GS_TEST_BUCKET}/streams/{audio._id}.mp4"
    assert audio.duration_ms == 29_000

    assert video.url == f"gs://{GS_TEST_BUCKET}/streams/{video._id}.mp4"
    assert video.duration_ms == 29_000

    filename = storage.get(audio.url, tmp_path)
    assert get_hash(filename) == \
        "0163fb2ee8772de9371c2cab6bc1f00c4063a2758ebef48a9a2bed510fc533d6"
    filename = storage.get(video.url, tmp_path)
    assert get_hash(filename) == \
        "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"
