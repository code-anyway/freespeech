from google import api_core
from google.cloud import tasks_v2

from freespeech import env
from freespeech.lib import hash
from freespeech.lib.tasks import results
from freespeech.types import Task

LOCATION = "us-central1"
QUEUE_NAME = "main"


def get_task_path(client, task_id):
    project = env.get_project_id()
    return client.task_path(project, LOCATION, QUEUE_NAME, task_id)


async def schedule(method: str, url: str, payload: bytes) -> Task:
    if method != "POST":
        raise ValueError("Only POST method is supported.")

    client = tasks_v2.CloudTasksClient()
    project = env.get_project_id()
    parent = client.queue_path(project, LOCATION, QUEUE_NAME)
    task_id = hash.string(payload.decode("utf-8"))
    task = {
        "name": get_task_path(client, task_id),
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,  # The full url path that the task will be sent to.
            "headers": {
                "Content-type": "application/json",
                # TODO (astaff): consider removing and relying on X-CloudTasks-TaskName
                "X-Freespeech-Task-ID": task_id,
            },
            "body": payload,
        },
    }

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
