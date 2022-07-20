from typing import Awaitable, BinaryIO, Sequence

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client import tasks
from freespeech.types import Audio, Error, IngestRequest, Media, Task, Video


async def ingest(
    *,
    source: str | BinaryIO,
    streams: Sequence[Audio | Video],
    session: aiohttp.ClientSession
) -> Awaitable[list[Media] | Error] | Error:
    request = IngestRequest(
        source=source if isinstance(source, str) else None,
        streams=streams,
    )

    with aiohttp.MultipartWriter("mixed") as mpwriter:
        mpwriter.append_json(pydantic_encoder(request))

        if isinstance(source, BinaryIO):
            mpwriter.append(source)

        async with session.post("/ingest", data=mpwriter) as resp:
            result = await resp.json()

            if resp.ok:
                return tasks.future(Task(**result), return_type=list[Media])
            else:
                return Error(**result)
