import asyncio
from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.client import save_stream_to_blob
from freespeech.client.errors import ok
from freespeech.client.tasks import Task
from freespeech.types import Error, IngestRequest, IngestResponse


async def ingest(
    source: str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
    *,
    filename: str | None = None,
    session: aiohttp.ClientSession,
) -> Task[IngestResponse] | Error:
    # todo (alex) replace this with the recommended pre-signed URL

    if not isinstance(source, str):
        assert filename
        source = await save_stream_to_blob(filename, source)

    request = IngestRequest(source=source)

    with aiohttp.MultipartWriter("form-data") as writer:
        writer.append_json(pydantic_encoder(request))

        if not request.source:
            part = writer.append(source)
            part.set_content_disposition("attachment", filename=filename)

        async with session.post("/api/media/ingest", data=writer) as resp:
            result = await resp.json()

            if ok(resp):
                return Task[IngestResponse](**result)
            else:
                return Error(**result)
