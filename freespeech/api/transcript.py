import logging
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any, BinaryIO, Dict, Type

import aiohttp
from aiohttp import BodyPartReader, web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech.client import client, media, tasks
from freespeech.lib import gdocs
from freespeech.lib import media as media_ops
from freespeech.lib import notion, speech, transcript, youtube
from freespeech.lib.storage import obj
from freespeech.types import (
    Audio,
    Error,
    IngestResponse,
    Language,
    LoadRequest,
    ServiceProvider,
    Source,
    SpeechToTextBackend,
    SynthesizeRequest,
    Transcript,
    assert_never,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


async def process(
    params: Dict,
    stream: Any | None,
    request_type: Type[SynthesizeRequest | LoadRequest],
    handler: Any,
) -> Dict:
    request = request_type(**params)
    # NOTE (astaff): IMO, we should have one base API per environment
    # and there should be a straightforward way to determine that from
    # the environment.
    session = client.create()
    return pydantic_encoder(await handler(request, stream, session))


async def _synthesize(
    request: SynthesizeRequest, stream: BinaryIO | None, session: aiohttp.ClientSession
) -> Transcript:
    with TemporaryDirectory() as tmp_dir:
        synth_file, _ = await speech.synthesize_events(
            events=request.transcript.events,
            lang=request.transcript.lang,
            output_dir=tmp_dir,
        )

        audio_url = None
        audio = request.transcript.audio and await media.probe(
            request.transcript.audio, session=session
        )
        if audio:
            audio_file = await obj.get(audio.url, dst_dir=tmp_dir)
            synth_file = await media_ops.mix(
                files=(audio_file, synth_file),
                weights=(request.transcript.settings.original_audio_level, 10),
                output_dir=tmp_dir,
            )

            with open(synth_file, "rb") as file:
                audio_url = (await _ingest(file, session)).audio

        video_url = None
        video = request.transcript.video and await media.probe(
            request.transcript.video, session=session
        )
        if video:
            video_file = await obj.get(video.url, dst_dir=tmp_dir)
            dub_file = await media_ops.dub(
                video=video_file, audio=synth_file, output_dir=tmp_dir
            )

            with open(dub_file, "rb") as file:
                video_url = (await _ingest(file, session)).video

    return replace(request.transcript, video=video_url, audio=audio_url)


async def _load(
    request: LoadRequest, stream: BinaryIO | None, session: aiohttp.ClientSession
) -> Transcript:
    source = request.source or stream
    if not source:
        raise ValueError("Missing source url or octet stream.")

    async def _decode(stream: BinaryIO) -> str:
        data = await stream.read()
        return data.decode("utf-8")

    match request.method:
        case "Google":
            if not isinstance(source, str):
                raise ValueError(f"Need a url for {request.method}.")
            return gdocs.load(source)
        case "Notion":
            if not isinstance(source, str):
                raise ValueError(f"Need a url for {request.method}.")
            return await notion.load(source)
        case "Machine A" | "Machine B" | "Machine C":
            asset = await _ingest(
                source=source,
                session=session,
            )
            if not asset.audio:
                raise ValueError(f"No audio stream: {source}")
            return await _transcribe(
                source=asset.audio,
                lang=request.lang,
                backend=request.method,
                session=session,
            )
        case "Subtitles":
            if not isinstance(source, str):
                raise ValueError(f"Need a url for {request.method}.")
            return Transcript(
                lang=request.lang,
                events=youtube.get_captions(source, lang=request.lang),
            )
        case "SRT":
            if not stream:
                raise ValueError(f"Need a binary stream for {request.method}.")
            text = await _decode(stream)
            events = transcript.srt_to_events(text)
            return Transcript(lang=request.lang, events=events)
        case "SSMD":
            if not stream:
                raise ValueError(f"Need a binary stream for {request.method}.")
            text = await _decode(stream)
            events = transcript.parse_events(text)
            return Transcript(lang=request.lang, events=events)
        case never:
            assert_never(never)


async def _transcribe(
    source: str,
    lang: Language,
    backend: SpeechToTextBackend,
    session: aiohttp.ClientSession,
) -> Transcript:
    provider: ServiceProvider
    match backend:
        case "Machine A":
            provider = "Google"
        case "Machine B":
            provider = "Deepgram"
        case "Machine C":
            provider = "Azure"
        case never:
            assert_never(never)

    audio = await media.probe(source=source, session=session)
    assert isinstance(audio.info, Audio)

    # TODO (astaff): Downsample to single channel here?

    events = await speech.transcribe(
        uri=audio.url, audio=audio.info, lang=lang, provider=provider
    )

    url = source if isinstance(source, str) else audio

    return Transcript(source=Source(backend, url), lang=lang, events=events)


async def _ingest(
    source: str | BinaryIO, session: aiohttp.ClientSession
) -> IngestResponse:
    response = await media.ingest(source=source, session=session)
    result = await tasks.future(response)
    if isinstance(result, Error):
        raise RuntimeError(result.message)

    return result


@routes.post("/synthesize")
async def synthesize(request: web.Request) -> web.Response:
    params = await request.json()

    try:
        response = await process(params, None, SynthesizeRequest, _synthesize)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)


@routes.post("/load")
async def load(request: web.Request) -> web.Response:
    parts = await request.multipart()

    part = await parts.next()
    assert isinstance(part, BodyPartReader)

    params = await part.json()
    assert params

    stream = await parts.next()
    assert isinstance(stream, BodyPartReader)

    try:
        response = await process(params, stream, LoadRequest, _load)
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(response)
