from typing import BinaryIO

import aiohttp

from freespeech.types import Error, Job, Media


async def ingest(
    *, source: str | BinaryIO, session: aiohttp.ClientSession
) -> Job[Media] | Error:
    params = {
        "url": source,
    }

    async with session.post("/ingest", json=params) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)
