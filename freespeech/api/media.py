import asyncio
import logging
import os
import tempfile

from aiohttp import BodyPartReader, web
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.lib import concurrency, hash, youtube
from freespeech.lib.storage import obj
from freespeech.types import IngestRequest, IngestResponse

logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post("/ingest")
async def ingest(web_request: web.Request) -> web.Response:
    parts = await web_request.multipart()

    part = await parts.next()
    assert isinstance(part, BodyPartReader)

    params = await part.json()
    assert params

    request = IngestRequest(**params)

    source = request.source
    if not source:
        raise NotImplementedError("Binary streams are not supported yet.")

    hashed_url = hash.string(source)

    audio_url = f"{env.get_storage_url()}/media/audio_{hashed_url}"
    video_url = f"{env.get_storage_url()}/media/video_{hashed_url}"

    with tempfile.TemporaryDirectory() as tempdir:
        audio_path = os.path.join(tempdir, f"{hashed_url}.audio")
        video_path = os.path.join(tempdir, f"{hashed_url}.video")

        os.mkfifo(audio_path)
        os.mkfifo(video_path)

        def _download():
            youtube.download(source, tempdir, audio_path, video_path, 4)

        await asyncio.gather(
            concurrency.run_in_thread_pool(_download),
            obj.put(audio_path, audio_url),
            obj.put(video_path, video_url),
        )

        result = IngestResponse(
            audio=obj.public_url(audio_url), video=obj.public_url(video_url)
        )
        return web.json_response(pydantic_encoder(result))
