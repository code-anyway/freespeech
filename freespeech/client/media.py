import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Awaitable, BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.client.tasks import Task
from freespeech.lib.storage import obj
from freespeech.types import Error, IngestRequest, IngestResponse

BUFFER_SIZE = 65535


async def _read_chunk(
    stream: aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
) -> bytes:
    result = stream.read(BUFFER_SIZE)
    if isinstance(result, Awaitable):
        return await result
    else:
        return result


async def _save(
    filename: str, stream: aiohttp.StreamReader | asyncio.StreamReader | BinaryIO
) -> str:
    filename = f"{str(uuid.uuid4())}{Path(filename).suffix}"
    blob_url = f"{env.get_storage_url()}/blobs/{filename}"

    with tempfile.TemporaryDirectory() as temp_dir:
        video_file = Path(temp_dir) / filename
        with open(video_file, "wb") as file:
            while chunk := await _read_chunk(stream):
                file.write(chunk)
        await obj.put(video_file, blob_url)

    return blob_url


async def ingest(
    source: str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
    *,
    filename: str | None = None,
    session: aiohttp.ClientSession,
) -> Task[IngestResponse] | Error:
    # todo (alex) replace this with the recommended pre-signed URL

    if not isinstance(source, str):
        assert filename
        source = await _save(filename, source)

    request = IngestRequest(source=source)

    with aiohttp.MultipartWriter("form-data") as writer:
        writer.append_json(pydantic_encoder(request))

        if not request.source:
            part = writer.append(source)
            part.set_content_disposition("attachment", filename=filename)

        async with session.post("/api/media/ingest", data=writer) as resp:
            result = await resp.json()

            if resp.ok:
                return Task[IngestResponse](**result)
            else:
                return Error(**result)
