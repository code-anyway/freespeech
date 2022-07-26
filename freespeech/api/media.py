import asyncio
import logging
import os
import tempfile

from freespeech.lib.hash import string as hash_string

import aiohttp.web_request
from aiohttp import BodyPartReader, web

from freespeech import env
from freespeech.lib import media, youtube, concurrency
from freespeech.lib.storage import doc, obj
from freespeech.types import IngestRequest

logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post("/ingest")
async def ingest(request: aiohttp.web_request.Request):
    # 1. handle multipart, reconstruct the stream and json meta
    multipart = await request.multipart()
    metadata_part = await multipart.next()
    assert isinstance(metadata_part, BodyPartReader)
    json = await metadata_part.json()
    assert json
    ingest_request = IngestRequest(**json)

    source = ingest_request.source

    hashed_url = hash_string(source)
    audio_url = f"{env.get_storage_url()}/media/audio_{hashed_url}"
    video_url = f"{env.get_storage_url()}/media/video_{hashed_url}"

    with tempfile.TemporaryDirectory() as tempdir:
        audio_fifo = f"{hashed_url}.audio"
        video_fifo = f"{hashed_url}.video"
        os.mkfifo(os.path.join(tempdir, audio_fifo))
        os.mkfifo(os.path.join(tempdir, video_fifo))

        def _download():
            youtube.download(source, tempdir, audio_fifo, video_fifo, 4)

        await asyncio.gather(
            concurrency.run_in_thread_pool(_download),
            obj.put(os.path.join(tempdir, audio_fifo), audio_url),
            obj.put(os.path.join(tempdir, video_fifo), video_url),
        )

        #todo return task here
        return web.json_response({})
