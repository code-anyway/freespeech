from aiohttp import web
from freespeech.services import crud
import pytest

ANNOUNCERS_TEST_VIDEO_URL = "https://youtu.be/bhRaND9jiOA"


@pytest.mark.asyncio
async def test_clip_upload_and_get(aiohttp_client):
    app = web.Application()
    # fill route table
    app.add_routes(crud.routes)
    client = await aiohttp_client(app)

    params = {
        "url": ANNOUNCERS_TEST_VIDEO_URL,
        "lang": "en-US"
    }

    resp = await client.post('/clips/upload', json=params)
    clip = await resp.json()

    resp = await client.get(f"/clips/{clip['_id']}")
    assert clip == await resp.json()
