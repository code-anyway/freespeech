import json

from aiohttp import web

from freespeech.lib.storage import doc


@web.middleware
async def persist_results(request, handler):
    resp = await handler(request)

    if resp.status < 400:
        result = resp.text
        task_id = request.headers.get("X-Freespeech-Task-ID", None)
        if task_id is not None:
            client = doc.google_firestore_client()
            await doc.put(client, "results", task_id, json.loads(result))

    return resp
