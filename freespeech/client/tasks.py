from typing import Awaitable, Sequence, Type

from freespeech.types import Error, Task, TaskReturnType


def future(
    task: Task, return_type: Type[TaskReturnType]
) -> Awaitable[TaskReturnType | Error]:
    async def _run() -> TaskReturnType | Error:
        pass

    return _run()


def tasks() -> Sequence[Task]:
    pass
