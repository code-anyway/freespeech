from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.types import Audio, Error, IngestRequest, IngestResponse, Media, Video


async def ingest(
    source: str | BinaryIO, *, session: aiohttp.ClientSession
) -> Task[IngestResponse] | Error:
    request = IngestRequest(
        source=source if isinstance(source, str) else None,
    )

    with aiohttp.MultipartWriter("mixed") as mpwriter:
        mpwriter.append_json(pydantic_encoder(request))

        if isinstance(source, BinaryIO):
            mpwriter.append(source)

        async with session.post("/ingest", data=mpwriter) as resp:
            result = await resp.json()

            if resp.ok:
                return Task[IngestResponse](**result)
            else:
                return Error(**result)


async def probe(
    source: str, *, session: aiohttp.ClientSession
) -> Media[Audio] | Media[Video]:
    raise NotImplementedError()
