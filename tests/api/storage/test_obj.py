import uuid

from freespeech.api.storage import obj

GS_TEST_BUCKET = "freespeech-tests"


def do_put_get(tmp_path, prefix):
    src_file = tmp_path / f"{uuid.uuid4()}.txt"
    src_file.write_text("Hello Local World!")

    download_path = tmp_path / "downloads"
    download_path.mkdir()

    dst_file = f"{uuid.uuid4()}.txt"
    url = f"{prefix}/{dst_file}"

    obj.put(src_file, url)
    assert obj.get(url, download_path) == str(download_path / dst_file)

    assert (download_path / dst_file).read_text() == "Hello Local World!"


def test_put_get_local(tmp_path):
    do_put_get(tmp_path, f"file://{tmp_path}")


def test_put_get_google_cloud_storage(tmp_path):
    do_put_get(tmp_path, f"gs://{GS_TEST_BUCKET}/test_storage")
