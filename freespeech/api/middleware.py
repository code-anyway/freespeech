import json
import logging

import aiohttp
from aiohttp import ClientResponseError, web

from freespeech.lib.storage import doc

logger = logging.getLogger(__name__)


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


@web.middleware
async def error_handler_middleware(request, handler):
    """Here we handle specific types of errors we know should be 'recoverable' or
    'user input errors', log them, and convert to HTTP Semantics"""
    try:
        resp = await handler(request)
        return resp
    except (AttributeError, NameError, ValueError, PermissionError, RuntimeError) as e:
        logger.warning(f"User input error: {e}", exc_info=e)
        raise web.HTTPBadRequest(text=str(e)) from e
    except ClientResponseError as e:
        logger.warning(f"Downstream api call error: {e}", exc_info=e)
        raise web.HTTPBadRequest(text=e.message) from e
    except aiohttp.web.HTTPError as e:
        logger.warning(f"HTTPError: {e}", exc_info=e)
        raise e
