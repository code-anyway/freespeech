import json

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.types import (
    Error,
    Job,
    Message,
)


async def ask(*, request: Message, session: aiohttp.ClientSession) -> Job | Error:
    text = json.dumps(request, default=pydantic_encoder)

    async with session.post("/ask", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)
