import logging
import uuid
from typing import Dict

from google import api_core
from google.cloud import tasks_v2
from google.protobuf import duration_pb2

from freespeech import env
from freespeech.lib.tasks import results
from freespeech.types import Task

LOCATION = "us-central1"
QUEUE_NAME = "main"
TASK_TIMEOUT_SEC = 30 * 60

logger = logging.getLogger(__name__)


def get_task_path(client, task_id):
    project = env.get_project_id()
    return client.task_path(project, LOCATION, QUEUE_NAME, task_id)


async def schedule(method: str, url: str, headers: Dict, payload: bytes) -> Task:
    if method != "POST":
        raise ValueError("Only POST method is supported.")

    client = tasks_v2.CloudTasksClient()
    project = env.get_project_id()
    parent = client.queue_path(project, LOCATION, QUEUE_NAME)
    task_id = str(uuid.uuid4())
    task = {
        "name": get_task_path(client, task_id),
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,  # The full url path that the task will be sent to.
            "headers": {
                "Content-Type": headers["Content-Type"],
                # TODO (astaff): consider removing and relying on X-CloudTasks-TaskName
                "X-Freespeech-Task-ID": task_id,
            },
            "body": payload,
        },
    }

    # Add dispatch deadline for requests sent to the worker.
    # more here: https://github.com/googleapis/python-tasks/issues/93
    duration = duration_pb2.Duration()
    dispatch_deadline = duration.FromSeconds(TASK_TIMEOUT_SEC)  # type: ignore
    logger.warning(f"Setting dispatch_deadline to {dispatch_deadline}")
    task["dispatch_deadline"] = dispatch_deadline

    client.create_task(request={"parent": parent, "task": task})

    return Task(
        state="Pending",
        id=task_id,
    )


async def get(id: str) -> Task:
    try:
        task_client = tasks_v2.CloudTasksClient()
        request = tasks_v2.GetTaskRequest(
            name=get_task_path(task_client, id),
        )
        task_client.get_task(request=request)
    # Successfully completed tasks are removed from the queue.
    except api_core.exceptions.NotFound:
        return await results.get(id)
    return Task(state="Pending", id=id, result=None)
