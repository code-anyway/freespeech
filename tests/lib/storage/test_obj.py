import uuid

import aiohttp
import pytest

from freespeech.lib.storage import obj

GS_TEST_BUCKET = "freespeech-tests"


@pytest.mark.asyncio
async def test_open():
    url = f"gs://{GS_TEST_BUCKET}/test_open/{uuid.uuid4()}"
    with obj.stream(url, "w") as blob:
        blob.write("Hello world!")

    with obj.stream(url, "r") as blob:
        assert blob.read() == "Hello world!"


@pytest.mark.asyncio
async def do_put_get(tmp_path, prefix):
    src_file = tmp_path / f"{uuid.uuid4()}.txt"
    src_file.write_text("Hello Local World!")

    download_path = tmp_path / "downloads"
    download_path.mkdir()

    dst_file = f"{uuid.uuid4()}.txt"
    url = f"{prefix}/{dst_file}"

    await obj.put(src_file, url)
    assert await obj.get(url, download_path) == str(download_path / dst_file)

    assert (download_path / dst_file).read_text() == "Hello Local World!"


@pytest.mark.asyncio
async def test_put_get_local(tmp_path):
    await do_put_get(tmp_path, f"file://{tmp_path}")


@pytest.mark.asyncio
async def test_put_get_google_cloud_storage(tmp_path):
    await do_put_get(tmp_path, f"gs://{GS_TEST_BUCKET}/test_storage")


@pytest.mark.asyncio
async def test_upload_content_type(tmp_path):
    location = f"test_open/video-{uuid.uuid4()}"
    url = f"gs://{GS_TEST_BUCKET}/{location}"

    await obj.put("tests/lib/data/media/ru-RU.mp4", url)

    public_url = obj.public_url(url)
    async with aiohttp.ClientSession() as session:
        async with session.head(public_url) as resp:
            assert resp.headers["Content-Type"] == "video/mp4"
