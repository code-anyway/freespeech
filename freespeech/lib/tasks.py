from google.cloud import tasks_v2

from freespeech import env
from freespeech.lib import hash
from freespeech.types import Task


def schedule(method: str, url: str, payload: bytes) -> Task:
    if method != "POST":
        raise ValueError("Only POST method is supported.")

    client = tasks_v2.CloudTasksClient()
    project = env.get_project_id()
    location = "us-central1"
    task_id = hash.string(payload.decode("utf-8"))
    queue_name = "main"
    parent = client.queue_path(project, location, queue_name)

    task = {
        "name": client.task_path(project, location, queue_name, task_id),
        "http_request": {  # Specify the type of request.
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,  # The full url path that the task will be sent to.
            "headers": {
                "Content-type": "application/json",
                "X-Freespeech-Task-ID": task_id,
            },
            "body": payload,
        },
    }

    response = client.create_task(request={"parent": parent, "task": task})

    return Task(
        state="Pending",
        id=response.name,
    )


def get(id: str) -> Task:
    # Look up ID in KV
    client = tasks_v2.CloudTasksClient()
    request = tasks_v2.GetTaskRequest(
        name=id,
    )
    response = client.get_task(request=request)
    result = response.last_attempt.response_status
    return result
