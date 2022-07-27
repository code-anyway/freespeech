import asyncio
import logging
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import BinaryIO, Sequence

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
    Event,
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
    request: LoadRequest,
    stream: aiohttp.StreamReader | None,
    session: aiohttp.ClientSession,
) -> Transcript:
    source = request.source or stream

    if not source:
        raise ValueError("Missing source url or octet stream.")

    async def _decode(stream: aiohttp.StreamReader) -> str:
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
            events = await _transcribe(
                source=asset.audio,
                lang=request.lang,
                backend=request.method,
                session=session,
            )
            return Transcript(
                lang=request.lang,
                events=events,
                source=Source(request.method, request.source or asset.audio),
                audio=asset.audio,
                video=asset.video,
            )
        case "Subtitles":
            if not isinstance(source, str):
                raise ValueError(f"Need a url for {request.method}.")
            asset = await _ingest(
                source=source,
                session=session,
            )
            return Transcript(
                lang=request.lang,
                audio=asset.audio,
                video=asset.video,
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
) -> Sequence[Event]:
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

    # audio = await media.probe(source=source, session=session)
    # assert isinstance(audio.info, Audio)

    audio_url = obj.storage_url(source)

    events = await speech.transcribe(
        uri=audio_url,
        audio=Audio(
            duration_ms=0, encoding="LINEAR16", sample_rate_hz=44100, num_channels=2
        ),
        lang=lang,
        provider=provider,
    )

    return events


async def _ingest(
    source: str | BinaryIO | aiohttp.StreamReader | asyncio.StreamReader,
    session: aiohttp.ClientSession,
) -> IngestResponse:
    response = await media.ingest(source=source, session=session)
    result = await tasks.future(response)
    if isinstance(result, Error):
        raise RuntimeError(result.message)

    return result


@routes.post("/synthesize")
async def synthesize(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        response = await _synthesize(
            request=SynthesizeRequest(**params), session=client.create()
        )
        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))


@routes.post("/load")
async def load(web_request: web.Request) -> web.Response:
    parts = await web_request.multipart()

    part = await parts.next()
    assert isinstance(part, BodyPartReader)

    params = await part.json()
    assert params

    try:
        request = LoadRequest(**params)
        stream = None

        if not isinstance(request.source, str):
            stream = await parts.next()
            assert isinstance(stream, BodyPartReader)

        response = await _load(
            request=LoadRequest(**params),
            stream=stream._content if stream else None,
            session=client.create(),
        )
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    return web.json_response(pydantic_encoder(response))
