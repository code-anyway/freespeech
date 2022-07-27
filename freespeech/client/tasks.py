from dataclasses import dataclass
from typing import Awaitable, Generic, Literal, Sequence, TypeVar

from freespeech.types import AskResponse, Error, IngestResponse, Operation, Transcript

TaskReturnType = TypeVar("TaskReturnType", Transcript, IngestResponse, AskResponse, str)


@dataclass(frozen=True)
class Task(Generic[TaskReturnType]):
    op: Operation
    state: Literal["Done", "Cancelled", "Running", "Pending", "Failed"]
    message: str | None
    id: str
    _future: Awaitable[TaskReturnType | Error]


def future(target: Task[TaskReturnType] | Error) -> Awaitable[TaskReturnType | Error]:
    async def _return_error(error):
        return error

    if isinstance(target, Error):
        return _return_error(target)

    async def _run() -> TaskReturnType | Error:
        # TODO: run the loop polling the future task service
        # If result is ready - return.
        # If still running - retry.
        # If error - wrap and return error.
        pass

    # TODO (astaff): Uncomment when we switch to server-side tasks
    # return _run()

    # TODO (astaff): This is a hack to simulate the behavior of
    # waiting for server-side task execution, while our services
    # are still synchronous
    return target._future


def tasks() -> Sequence[Task]:
    pass
