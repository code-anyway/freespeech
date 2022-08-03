import json

from aiohttp import web

from freespeech.lib.storage import doc


@web.middleware
async def persist_results(request, handler):
    """Writes result of an API call into document storage.

    This middleware is used in combination with task queue. Since the queue
    doesn't persist the results of a call, we have to do it
    ourselves.

    The value of `X-Freespeech-Task-ID` header is the primary key and is set by
    task scheduler."""
    resp = await handler(request)

    result = resp.text
    task_id = request.headers.get("X-Freespeech-Task-ID", None)
    if task_id is not None:
        client = doc.google_firestore_client()
        record = {"status": resp.status, "result": json.loads(result)}
        await doc.put(client, "results", task_id, record)

    return resp
