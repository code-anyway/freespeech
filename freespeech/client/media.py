from typing import Awaitable, BinaryIO, Sequence, Type

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client import tasks
from freespeech.types import Error, IngestRequest, Media, MediaType, Task


async def ingest(
    source: str | BinaryIO,
    *,
    output_types: Sequence[Type[MediaType]],
    session: aiohttp.ClientSession
) -> Awaitable[list[Media[MediaType]] | Error] | Error:
    request = IngestRequest(
        source=source if isinstance(source, str) else None,
        output_types=output_types,
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
