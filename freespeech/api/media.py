import logging
from dataclasses import asdict
from tempfile import TemporaryDirectory

import aiohttp.web_request
from aiohttp import BodyPartReader, web

from freespeech import env
from freespeech.lib import media, youtube
from freespeech.lib.storage import doc, obj
from freespeech.types import IngestRequest

logger = logging.getLogger(__name__)


routes = web.RouteTableDef()

# Todo rename actual file to Media?


# expecting multipart structure here
@routes.post("/ingest")
async def ingest(request: aiohttp.web_request.Request):
    # 1. handle multipart, reconstruct the stream and json meta
    multipart = await request.multipart()
    metadata_part = await multipart.next()
    assert isinstance(metadata_part, BodyPartReader)
    json = await metadata_part.json()
    assert json
    ingest_request = IngestRequest(**json)

    if not ingest_request.source:
        video_part = await multipart.next()
        # handle video by piping it to BinaryIO with video_part.read_chunk()
