import logging
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any, BinaryIO, Dict, Type

import aiohttp
from aiohttp import web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech.client import media as media_client
from freespeech.client import tasks
from freespeech.lib import gdocs, media, notion, speech
from freespeech.lib.storage import obj
from freespeech.types import (
    Error,
    IngestResponse,
    LoadRequest,
    SynthesizeRequest,
    Transcript,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


async def process(
    params: Dict, request_type: Type[SynthesizeRequest], handler: Any
) -> Dict:
    request = request_type(**params)
    return pydantic_encoder(await handler(request))


async def _synthesize(
    request: SynthesizeRequest, session: aiohttp.ClientSession
) -> Transcript:
    with TemporaryDirectory() as tmp_dir:
        synth_file, _ = await speech.synthesize_events(
            events=request.transcript.events,
            lang=request.transcript.lang,
            output_dir=tmp_dir,
        )

        audio_url = None
        audio = request.transcript.audio and await media_client.probe(
            request.transcript.audio, session=session
        )
        if audio:
            audio_file = await obj.get(audio.url, dst_dir=tmp_dir)
            synth_file = await media.mix(
                files=(audio_file, synth_file),
                weights=(request.transcript.settings.original_audio_level, 10),
                output_dir=tmp_dir,
            )

            with open(synth_file, "rb") as file:
                audio_url = (await _ingest_stream(file, session)).audio

        video_url = None
        video = request.transcript.video and await media_client.probe(
            request.transcript.video, session=session
        )
        if video:
            video_file = await obj.get(video.url, dst_dir=tmp_dir)
            dub_file = await media.dub(
                video=video_file, audio=synth_file, output_dir=tmp_dir
            )

            with open(dub_file, "rb") as file:
                video_url = (await _ingest_stream(file, session)).video

    return replace(request.transcript, video=audio_url, audio=video_url)


async def _load(request: LoadRequest) -> Transcript:
    if not request.source:
        raise ValueError("Missing source URL")

    match request.method:
        case "Google":
            return gdocs.load(request.source)
        case "Notion":
            return await notion.load(request.source)
    raise NotImplementedError()


async def _ingest_stream(
    stream: BinaryIO, session: aiohttp.ClientSession
) -> IngestResponse:
    response = await media_client.ingest(source=stream, session=session)

    if isinstance(response, Error):
        raise RuntimeError(response.message)

    result = await tasks.future(response)

    if isinstance(result, Error):
        raise RuntimeError(result.message)

    return result


@routes.post("/synthesize")
async def synthesize(request: web.Request) -> web.Response:
    params = await request.json()

    try:
        response = await process(params, SynthesizeRequest, _synthesize)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)


@routes.post("/load")
async def load(request):
    params = await request.json()

    try:
        response = await process(params, LoadRequest, _load)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)
