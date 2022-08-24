import functools
import json
import logging
from typing import Awaitable, Callable, Dict, Sequence, Type

import aiohttp
from aiohttp import BodyPartReader, web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.api import errors
from freespeech.types import (
    AskRequest,
    Error,
    IngestRequest,
    LoadRequest,
    RequestType,
    SaveRequest,
    SynthesizeRequest,
    Task,
    TranslateRequest,
)

ScheduleFunction = Callable[[str, str, Dict, bytes], Awaitable[Task]]
GetFunction = Callable[[str], Awaitable[Task]]

logger = logging.getLogger(__name__)


def routes(
    schedule_fn: ScheduleFunction, get_fn: GetFunction
) -> Sequence[web.RouteDef]:

    media_url = env.get_media_service_url()
    transcript_url = env.get_transcript_service_url()
    chat_url = env.get_chat_service_url()
    get = functools.partial(_get, get_fn)

    return [
        web.post(
            path="/api/media/ingest",
            handler=functools.partial(
                _handler, f"{media_url}/media/ingest", IngestRequest, schedule_fn
            ),
        ),
        web.post(
            path="/api/transcript/save",
            handler=functools.partial(
                _handler, f"{transcript_url}/transcript/save", SaveRequest, schedule_fn
            ),
        ),
        web.post(
            path="/api/transcript/load",
            handler=functools.partial(
                _handler, f"{transcript_url}/transcript/load", LoadRequest, schedule_fn
            ),
        ),
        web.post(
            path="/api/transcript/translate",
            handler=functools.partial(
                _handler,
                f"{transcript_url}/transcript/translate",
                TranslateRequest,
                schedule_fn,
            ),
        ),
        web.post(
            path="/api/transcript/synthesize",
            handler=functools.partial(
                _handler,
                f"{transcript_url}/transcript/synthesize",
                SynthesizeRequest,
                schedule_fn,
            ),
        ),
        web.post(
            path="/api/chat/ask",
            handler=functools.partial(
                _passthrough_handler, f"{chat_url}/chat/ask", AskRequest
            ),
        ),
        web.get(path="/api/tasks/{id}", handler=get),
    ]


async def _get(get_fn: GetFunction, web_request: web.Request) -> web.Response:
    id = web_request.match_info["id"]
    task = await get_fn(id)
    return web.json_response(pydantic_encoder(task))


async def _handler(
    url: str,
    request_type: Type[RequestType],
    schedule_fn: ScheduleFunction,
    web_request: web.Request,
) -> web.Response:
    try:
        request = await _build_request(request_type, web_request)
    except NotImplementedError as e:
        raise errors.input_error(Error(message=str(e)))
    except ValidationError as e:
        raise errors.input_error(Error(message=str(e)))

    task = await schedule_fn(
        web_request.method,
        url,
        dict(web_request.headers),
        json.dumps(pydantic_encoder(request)).encode("utf-8"),
    )

    return web.json_response(pydantic_encoder(task))


async def _passthrough_handler(
    url: str, request_type: Type[RequestType], web_request: web.Request
) -> web.Response:
    try:
        request = await _build_request(request_type, web_request)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=web_request.method,
                url=url,
                headers={"Content-Type": web_request.headers["Content-Type"]},
                data=json.dumps(pydantic_encoder(request)).encode("utf-8"),
            ) as response:
                return web.Response(
                    text=await response.text(),
                    content_type=response.content_type,
                    status=response.status,
                    reason=response.reason,
                )

    except ValidationError as e:
        raise errors.bad_request(Error(message=str(e)))


async def _build_request(
    request_type: Type[RequestType], web_request: web.Request
) -> RequestType:
    if request_type in (IngestRequest, LoadRequest):
        parts = await web_request.multipart()
        part = await parts.next()
        assert isinstance(part, BodyPartReader)
        params = await part.json()
        assert params is not None

        if params.get("source", None) is None:
            logger.error(
                f"Attempting to save multipart, should not happen. Request: {params}"
            )
            raise NotImplementedError("Stream upload via multipart not supported now")
    else:
        params = await web_request.json()
    assert params is not None
    return request_type(**params)
