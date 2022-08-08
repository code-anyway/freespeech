import asyncio

import aiohttp

from freespeech.types import Error, Task, TaskReturnType


async def future(
    target: Task[TaskReturnType] | Error,
    session: aiohttp.ClientSession,
    poll_interval_sec: float = 1.0,
) -> TaskReturnType | Error:
    if isinstance(target, Error):
        return target

    task = target

    while task.state == "Pending":
        task = await get(task.id, session)
        await asyncio.sleep(poll_interval_sec)

    if task.state == "Done":
        assert task.result
        return task.result

    if task.state == "Failed":
        return Error(f"Task failed: {task.result}")


async def get(id: str, session: aiohttp.ClientSession) -> Task[TaskReturnType]:
    async with session.get(f"/api/tasks/{id}") as resp:
        result = await resp.json()
        return Task(**result)
