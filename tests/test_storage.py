import uuid
from freespeech import storage

GS_TEST_BUCKET = "freespeech-tests"


def test_put_get_local(tmp_path):
    src_file = tmp_path / f"{uuid.uuid4()}.txt"
    src_file.write_text("Hello Local World!")

    download_path = tmp_path / "downloads"
    download_path.mkdir()

    dst_file = f"{uuid.uuid4()}.txt"
    url = f"file:///{tmp_path}/{dst_file}"

    storage.put(src_file, url)
    storage.get(url, download_path)

    assert (download_path / dst_file).read_text() == "Hello Local World!"


def test_put_get_google_cloud_storage(tmp_path):
    src_file = tmp_path / f"{uuid.uuid4()}.txt"
    src_file.write_text("Hello Cloud World!")

    download_path = tmp_path / "downloads"
    download_path.mkdir()

    dst_file = f"{uuid.uuid4()}.txt"
    url = f"gs://{GS_TEST_BUCKET}/test_storage/{dst_file}"

    storage.put(src_file, url)
    storage.get(url, download_path)

    assert (download_path / dst_file).read_text() == "Hello Cloud World!"
