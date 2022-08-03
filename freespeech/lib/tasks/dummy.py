import uuid

import aiohttp

from freespeech.lib.tasks import results
from freespeech.types import Error, Task


async def schedule(method: str, url: str, payload: bytes) -> Task:
    """Makes a synchronous call to downstream API endpoint."""
    async with aiohttp.ClientSession() as session:
        async with session.request(method=method, url=url, data=payload) as response:
            id = str(uuid.uuid4())

            if response.ok:
                return Task(state="Done", id=id, result=await response.json())
            else:
                if response.content_type == "application/json":
                    return Task(
                        state="Failed", id=id, result=Error(**await response.json())
                    )
                else:
                    return Task(
                        state="Failed",
                        id=id,
                        result=Error(message=await response.text()),
                    )


async def get(id: str) -> Task:
    return await results.get(id)
