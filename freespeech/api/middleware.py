import json
import logging

import aiohttp
from aiohttp import ClientResponseError, web
from aiohttp.web_exceptions import HTTPError

from freespeech.api import errors
from freespeech.api.errors import HTTPInputError
from freespeech.lib.storage import doc
from freespeech.types import Error

logger = logging.getLogger(__name__)


@web.middleware
async def persist_results(request, handler):
    """Writes result of an API call into document storage.

    This middleware is used in combination with task queue. Since the queue
    doesn't persist the results of a call, we have to do it
    ourselves.

    The value of `X-Freespeech-Task-ID` header is the primary key and is set by
    task scheduler."""

    task_id = request.headers.get("X-Freespeech-Task-ID", None)
    # This means we've been called outside of Cloud Tasks context, so passthrough
    if task_id is None:
        return await handler(request)

    client = doc.google_firestore_client()
    try:
        resp = await handler(request)

        result = resp.text
        record = {"status": resp.status, "result": json.loads(result)}
        await doc.put(client, "results", task_id, record)

        return resp
    except Exception as e:
        status = 500
        message = str(e)
        if isinstance(e, HTTPError):
            status = e.status
        if isinstance(e, HTTPInputError):
            # Since by HTTP means it is a Success (2xx), we handle it separately.
            status = e.status
            message = e.text
        if isinstance(e, ClientResponseError) and e.status:
            status = e.status

        record = {"status": status, "result": message}
        await doc.put(client, "results", task_id, record)

        raise e


@web.middleware
async def error_handler_middleware(request, handler):
    """Here we handle specific types of errors we know should be 'recoverable' or
    'user input errors', log them, and convert to HTTP Semantics"""
    try:
        resp = await handler(request)
        return resp
    except (AttributeError, NameError, ValueError, PermissionError) as e:
        logger.warning(f"User input error: {e}", exc_info=e)
        raise errors.input_error(Error(message=str(e)))
    except (RuntimeError) as e:
        logger.warning(f"Runtime Error, maybe due to user input: {e}", exc_info=e)
        raise errors.bad_request(Error(message=str(e))) from e
    except ClientResponseError as e:
        logger.warning(f"Downstream api call error: {e}", exc_info=e)
        raise errors.bad_request(Error(message=str(e.message))) from e
    except aiohttp.web.HTTPError as e:
        logger.warning(f"HTTPError: {e}", exc_info=e)
        raise e
