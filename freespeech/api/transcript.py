import logging
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any, Dict, Type

from aiohttp import web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.lib import gdocs, media, notion, speech
from freespeech.lib.storage import obj
from freespeech.types import (
    Audio,
    Error,
    LoadRequest,
    Media,
    SynthesizeRequest,
    Transcript,
    Video,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


async def process(
    params: Dict, request_type: Type[SynthesizeRequest], handler: Any
) -> Dict:
    request = request_type(**params)
    return pydantic_encoder(await handler(request))


async def _synthesize(request: SynthesizeRequest) -> Transcript:
    with TemporaryDirectory() as tmp_dir:
        synth_file, _ = await speech.synthesize_events(
            events=request.transcript.events,
            lang=request.transcript.lang,
            output_dir=tmp_dir,
        )
        audio_file = request.transcript.audio
        )
        video_file = request.transcript.video and await obj.get(
            request.transcript.video.url, dst_dir=tmp_dir
        )
        mixed_file = await media.mix(
            files=(audio_file, synth_file),
            weights=(request.transcript.settings.original_audio_level, 10),
            output_dir=tmp_dir,
        )
        dub_file = await media.dub(
            video=video_file, audio=mixed_file, output_dir=tmp_dir
        )
        dub_url = f"{env.get_storage_url()}/output/{dub_file.name}"
        await obj.put(dub_file, dub_url)

    return replace(
        request.transcript,
        video=Media[Video](
            url=dub_url,
            info=None,
        ),
        audio=Media[Audio](
            url=dub_url,
            info=None,
        ),
    )


@routes.post("/synthesize")
async def synthesize(request: web.Request) -> web.Response:
    params = await request.json()

    try:
        response = await process(params, SynthesizeRequest, _synthesize)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)


async def _load(request: LoadRequest) -> Transcript:
    if not request.source:
        raise ValueError("Missing source URL")

    match request.method:
        case "Google":
            return gdocs.load(request.source)
        case "Notion":
            return await notion.load(request.source)
    raise NotImplementedError()


@routes.post("/load")
async def load(request):
    params = await request.json()

    try:
        response = await process(params, LoadRequest, _load)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)
