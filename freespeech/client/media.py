import asyncio
import json
from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.lib import hash
from freespeech.types import Error, IngestRequest, IngestResponse


async def ingest(
    source: str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
    *,
    filename: str | None = None,
    session: aiohttp.ClientSession
) -> Task[IngestResponse] | Error:
    request = IngestRequest(
        source=source if isinstance(source, str) else None,
    )

    async def _future() -> IngestResponse | Error:
        with aiohttp.MultipartWriter("form-data") as writer:
            writer.append_json(pydantic_encoder(request))

            if not request.source:
                part = writer.append(source)
                part.set_content_disposition("attachment", filename=filename)

            async with session.post("/ingest", data=writer) as resp:
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
