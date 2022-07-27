import asyncio
import json
from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.lib import hash
from freespeech.types import Audio, Error, IngestRequest, IngestResponse, Media, Video


async def ingest(
    source: str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
    *,
    session: aiohttp.ClientSession
) -> Task[IngestResponse] | Error:
    request = IngestRequest(
        source=source if isinstance(source, str) else None,
    )

    async def _future() -> IngestResponse | Error:
        with aiohttp.MultipartWriter("form-data") as mpwriter:
            mpwriter.append_json(pydantic_encoder(request))

            match source:
                case str():
                    pass
                case aiohttp.StreamReader | asyncio.StreamReader:
                    mpwriter.append(source)
                case BinaryIO():
                    mpwriter.append(source)

            async with session.post("/ingest", data=mpwriter) as resp:
                result = await resp.json()

                if resp.ok:
                    return IngestResponse(**result)
                else:
                    return Error(**result)

    return Task[IngestResponse](
        state="Running",
        op="Transcribe",
        id=hash.string(json.dumps(pydantic_encoder(request))),
        message="Estimated wait time: 10 minutes",
        _future=_future(),
    )


async def probe(
    source: str, *, session: aiohttp.ClientSession
) -> Media[Audio] | Media[Video]:
    raise NotImplementedError()
