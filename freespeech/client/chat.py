from typing import Dict

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.types import AskRequest, Error, Operation, Task


async def ask(
    *,
    message: str,
    intent: Operation | None,
    state: Dict,
    session: aiohttp.ClientSession
) -> Task | Error:
    request = AskRequest(message=message, intent=intent, state=state)

    async with session.post("/ask", json=pydantic_encoder(request)) as resp:
        result = await resp.json()

        if resp.ok:
            return Task(**result)
        else:
            return Error(**result)
