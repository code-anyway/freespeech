import asyncio
import logging
import os
import tempfile

from aiohttp import web
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.lib import concurrency, hash, youtube
from freespeech.lib.storage import obj
from freespeech.types import IngestRequest, IngestResponse

logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post("/media/ingest")
async def ingest(web_request: web.Request) -> web.Response:
    params = await web_request.json()
    request = IngestRequest(**params)

    if request.source is None:
        raise ValueError("Missing source URL")
    else:
        source = request.source

    if source.startswith("gs://"):
        result = IngestResponse(
            audio=obj.public_url(source),
            video=obj.public_url(source),
        )

        return web.json_response(pydantic_encoder(result))
    else:
        hashed_url = hash.string(source)

        audio_url = f"{env.get_storage_url()}/media/a_{hashed_url}.wav"
        video_url = f"{env.get_storage_url()}/media/v_{hashed_url}.mp4"

        with tempfile.TemporaryDirectory() as tempdir:
            audio_path = os.path.join(tempdir, f"{hashed_url}.wav")
            video_path = os.path.join(tempdir, f"{hashed_url}.mp4")

            os.mkfifo(audio_path)
            os.mkfifo(video_path)

            await asyncio.gather(
                concurrency.run_in_thread_pool(
                    lambda: youtube.download(source, tempdir, audio_path, video_path, 4)
                ),
                obj.put(audio_path, audio_url),
                obj.put(video_path, video_url),
            )

            result = IngestResponse(
                audio=obj.public_url(audio_url),
                video=obj.public_url(video_url),
            )
            return web.json_response(pydantic_encoder(result))
