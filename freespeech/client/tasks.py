import asyncio
from typing import Awaitable, Sequence

from freespeech.types import Error, Task, TaskReturnType


def future(
    target: Task[TaskReturnType] | Error, poll_interval_sec: float = 1.0
) -> Awaitable[TaskReturnType | Error]:
    async def _return_error(error):
        return error

    if isinstance(target, Error):
        return _return_error(target)

    async def _run():
        task = target
        while task.state != "Done":
            raise NotImplementedError("poll tasks/get(id)")
            task = tasks.get(task.id)
            await asyncio.sleep(poll_interval_sec)
        assert target.state == "Done"
        result = target.result
        return result

    return _run()


async def get(id: str) -> Task[TaskReturnType]:
    pass


def tasks() -> Sequence[Task]:
    pass
