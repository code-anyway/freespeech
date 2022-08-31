from typing import Dict

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.types import AskRequest, Error, Operation, Transcript


async def ask(
    *,
    message: str,
    intent: Operation | None,
    state: Dict,
    session: aiohttp.ClientSession
) -> Task[Transcript] | Error:
    request = AskRequest(message=message, intent=intent, state=state)

    async with session.post("/api/chat/ask", json=pydantic_encoder(request)) as resp:
        result = await resp.json()

        if resp.ok and resp.status != 299:
            return Task[Transcript](**result)
        else:
            return Error(**result)
