import json
from typing import Dict

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.lib import hash
from freespeech.types import AskRequest, AskResponse, Error, Operation


async def ask(
    *,
    message: str,
    intent: Operation | None,
    state: Dict,
    session: aiohttp.ClientSession
) -> Task[AskResponse] | Error:
    request = AskRequest(message=message, intent=intent, state=state)

    async def _future() -> AskResponse | Error:
        async with session.post("/chat/ask", json=pydantic_encoder(request)) as resp:
            result = await resp.json()

            if resp.ok:
                return AskResponse(**result)
            else:
                return Error(**result)

    return Task[AskResponse](
        state="Running",
        op="Transcribe",
        id=hash.string(json.dumps(pydantic_encoder(request))),
        message="Estimated wait time: 10 minutes",
        _future=_future(),
    )
