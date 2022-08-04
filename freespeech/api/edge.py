import functools
import json
import tempfile
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Sequence, Type

from aiohttp import BodyPartReader, web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.api import errors
from freespeech.lib.storage import obj
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

ScheduleFunction = Callable[[str, str, bytes], Awaitable[Task]]
GetFunction = Callable[[str], Awaitable[Task]]


def routes(
    schedule_fn: ScheduleFunction, get_fn: GetFunction
) -> Sequence[web.RouteDef]:
    handler = functools.partial(_handler, schedule_fn)
    get = functools.partial(_get, get_fn)

    return [
        web.post(path="/api/{service:media}/{endpoint:ingest}", handler=handler),
        web.post(path="/api/{service:transcript}/{endpoint:save}", handler=handler),
        web.post(path="/api/{service:transcript}/{endpoint:load}", handler=handler),
        web.post(
            path="/api/{service:transcript}/{endpoint:translate}", handler=handler
        ),
        web.post(
            path="/api/{service:transcript}/{endpoint:synthesize}", handler=handler
        ),
        web.post(path="/api/{service:chat}/{endpoint:ask}", handler=handler),
        web.get(path="/api/tasks/{id}", handler=get),
    ]


async def _get(get_fn: GetFunction, web_request: web.Request) -> web.Response:
    id = web_request.match_info["id"]
    task = await get_fn(id)
    return web.json_response(pydantic_encoder(task))


async def _handler(
    schedule_fn: ScheduleFunction, web_request: web.Request
) -> web.Response:
    service = web_request.match_info["service"]
    endpoint = web_request.match_info["endpoint"]

    service_urls = {
        "media": env.get_media_service_url(),
        "transcript": env.get_transcript_service_url(),
        "chat": env.get_chat_service_url(),
    }

    url = service_urls.get(service, None)
    if not url:
        raise errors.bad_request(Error(f"Unknown service: {service}"))

    endpoint_request_types = {
        "synthesize": SynthesizeRequest,
        "save": SaveRequest,
        "translate": TranslateRequest,
        "ask": AskRequest,
        "load": LoadRequest,
        "ingest": IngestRequest,
        "synthesize": SynthesizeRequest,
    }
    request_type = endpoint_request_types.get(endpoint, None)
    if not request_type:
        raise errors.bad_request(Error(f"Unknown endpoint: {endpoint}"))

    try:
        request = await _build_request(request_type, web_request)
    except ValidationError as e:
        raise errors.bad_request(Error(message=str(e)))

    task = await schedule_fn(
        web_request.method,
        f"{url}/{service}/{endpoint}",
        json.dumps(pydantic_encoder(request)).encode("utf-8"),
    )

    return web.json_response(pydantic_encoder(task))


async def _save(stream: BodyPartReader) -> str:
    assert stream.filename is not None
    filename = f"{str(uuid.uuid4())}{Path(stream.filename).suffix}"
    blob_url = f"{env.get_storage_url()}/blobs/{filename}"

    with tempfile.TemporaryDirectory() as temp_dir:
        video_file = Path(temp_dir) / filename
        with open(video_file, "wb") as file:
            file.write(await stream.read())
        await obj.put(video_file, blob_url)

    return blob_url


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
            stream = await parts.next()
            assert isinstance(stream, BodyPartReader)
            blob_url = await _save(stream)
            params = {**params, "source": blob_url}
    else:
        params = await web_request.json()
    assert params is not None
    return request_type(**params)
