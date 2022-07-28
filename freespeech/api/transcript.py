import asyncio
import json
import logging
import tempfile
from dataclasses import replace
from io import BytesIO
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
    Error,
    Event,
    IngestResponse,
    Language,
    LoadRequest,
    SaveRequest,
    SaveResponse,
    ServiceProvider,
    Source,
    SpeechToTextBackend,
    SynthesizeRequest,
    Transcript,
    assert_never,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


# Events with the gap greater than GAP_MS won't be concatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600

# When there is a speech break, we will end sentence and start a new one.
TRANSCRIPT_NORMALIZATION: speech.Normalization = "break_ends_sentence"


async def _save(request: SaveRequest) -> SaveResponse:
    match request.method:
        case "Google":
            return SaveResponse(url=gdocs.create(request.transcript))
        case "Notion":
            if request.location is None:
                raise ValueError("For Notion `location` should be set to Database ID.")
            _, url, _ = await notion.create(
                request.transcript, database_id=request.location
            )
            return SaveResponse(url=url)
        case "SSMD":
            return SaveResponse(
                url=gdocs.create_from_text(
                    title=request.transcript.title,
                    text=transcript.render_transcript(request.transcript),
                )
            )
        case "SRT":
            return SaveResponse(
                url=gdocs.create_from_text(
                    title=request.transcript.title,
                    text=transcript.events_to_srt(request.transcript.events),
                )
            )
        case "Subtitles":
            plain_text = "\n\n".join(
                "\n".join(event.chunks) for event in request.transcript.events
            )
            return SaveResponse(
                url=gdocs.create_from_text(
                    title=request.transcript.title, text=plain_text
                )
            )
        case "Machine A" | "Machine B" | "Machine C":
            raise ValueError(f"Unsupported method: {request.method}")
        case never:
            assert_never(never)


async def _synthesize(
    request: SynthesizeRequest, session: aiohttp.ClientSession
) -> Transcript:
    with TemporaryDirectory() as tmp_dir:
        synth_file, _ = await speech.synthesize_events(
            events=request.transcript.events,
            lang=request.transcript.lang,
            output_dir=tmp_dir,
        )

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
            audio_url = (await _ingest(file, str(synth_file), session)).audio

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
                video_url = (await _ingest(file, str(synth_file), session)).video

    return replace(request.transcript, video=video_url, audio=audio_url)


async def _load(
    request: LoadRequest,
    stream: aiohttp.StreamReader | BodyPartReader | None,
    session: aiohttp.ClientSession,
) -> Transcript:
    source = request.source or stream

    if not source:
        raise ValueError("Missing source url or octet stream.")

    async def _decode(data: bytes) -> str:
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
                source if isinstance(source, str) else BytesIO(await source.read()),
                filename=None,
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
            result = Transcript(
                lang=request.lang,
                events=events,
                source=Source(request.method, request.source or asset.audio),
                audio=asset.audio,
                video=asset.video,
            )
            return _normalize_speech(result, method=TRANSCRIPT_NORMALIZATION)
        case "Subtitles":
            if not isinstance(source, str):
                raise ValueError(f"Need a url for {request.method}.")
            asset = await _ingest(
                source=source,
                filename=None,
                session=session,
            )
            result = Transcript(
                source=Source(method=request.method, url=request.source),
                lang=request.lang,
                audio=asset.audio,
                video=asset.video,
                events=youtube.get_captions(source, lang=request.lang),
            )
            return _normalize_speech(result, method=TRANSCRIPT_NORMALIZATION)
        case "SRT":
            if not stream:
                raise ValueError(f"Need a binary stream for {request.method}.")
            text = await _decode(await stream.read())
            events = transcript.srt_to_events(text)
            return Transcript(
                source=Source(method=request.method, url=None),
                lang=request.lang,
                events=events,
            )
        case "SSMD":
            if not stream:
                raise ValueError(f"Need a binary stream for {request.method}.")
            text = await _decode(await stream.read())
            events = transcript.parse_events(text)
            return Transcript(
                source=Source(method=request.method, url=None),
                lang=request.lang,
                events=events,
            )
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

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_file = await obj.get(obj.storage_url(source), tmp_dir)
        output_mono = await media_ops.multi_channel_audio_to_mono(audio_file, tmp_dir)
        with open(output_mono, "rb") as file:
            task = await media.ingest(file, filename=str(output_mono), session=session)
            result = await tasks.future(task)
            if isinstance(result, Error):
                raise RuntimeError(result.message)
            assert result.audio is not None

    events = await speech.transcribe(
        uri=obj.storage_url(result.audio),
        lang=lang,
        provider=provider,
    )

    return events


def _normalize_speech(
    transcript: Transcript, method: speech.Normalization
) -> Transcript:
    return replace(
        transcript,
        events=speech.normalize_speech(
            transcript.events,
            gap_ms=GAP_MS,
            length=PHRASE_LENGTH,
            method=method
        )
    )


async def _ingest(
    source: str | BinaryIO | aiohttp.StreamReader | asyncio.StreamReader,
    filename: str | None,
    session: aiohttp.ClientSession,
) -> IngestResponse:
    response = await media.ingest(source=source, filename=filename, session=session)
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
        raise web.HTTPBadRequest(
            text=json.dumps(pydantic_encoder(error)), content_type="application/json"
        )


@routes.post("/save")
async def save(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        response = await _save(request=SaveRequest(**params))
        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(
            text=json.dumps(pydantic_encoder(error)), content_type="application/json"
        )


@routes.post("/load")
async def load(web_request: web.Request) -> web.Response:
    parts = await web_request.multipart()

    part = await parts.next()
    assert isinstance(part, BodyPartReader)

    params = await part.json()
    assert params

    try:
        request = LoadRequest(**params)

        if isinstance(request.source, str):
            response = await _load(
                request=LoadRequest(**params),
                stream=None,
                session=client.create(),
            )
        else:
            stream = await parts.next()
            assert isinstance(stream, BodyPartReader)
            response = await _load(
                request=LoadRequest(**params),
                stream=stream,
                session=client.create(),
            )

    except (ValidationError, ValueError) as e:
        error = Error(message=str(e))
        raise web.HTTPBadRequest(
            text=json.dumps(pydantic_encoder(error)), content_type="application/json"
        )

    return web.json_response(pydantic_encoder(response))
