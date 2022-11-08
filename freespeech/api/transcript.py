import asyncio
import logging
import tempfile
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import BinaryIO

import aiohttp
from aiohttp import web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech.api import errors
from freespeech.client import client, media, tasks
from freespeech.lib import gdocs, language
from freespeech.lib import media as media_ops
from freespeech.lib import notion, speech, youtube
from freespeech.lib.storage import obj
from freespeech.types import (
    TRANSCRIPT_PLATFORMS,
    Error,
    IngestResponse,
    Language,
    LoadRequest,
    MediaPlatform,
    Method,
    SaveRequest,
    SaveResponse,
    ServiceProvider,
    Settings,
    SynthesizeRequest,
    Transcript,
    TranscriptionModel,
    TranscriptPlatform,
    TranslateRequest,
    assert_never,
    is_transcript_platform,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


# Events with the gap greater than GAP_MS won't be concatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600

# When there is a speech break, we will end sentence and start a new one.
TRANSCRIPT_NORMALIZATION: speech.Normalization = "break_ends_sentence"


def _platform(source: str | BinaryIO) -> TranscriptPlatform | MediaPlatform:
    if isinstance(source, BinaryIO):
        return "Stream"
    if source.startswith("https://docs.google.com/document/d/"):
        return "Google"
    if source.startswith("https://www.notion.so/"):
        return "Notion"
    if (
        source.startswith("https://www.youtube.com/")
        or source.startswith("https://youtu.be/")
        or source.startswith("https://m.youtube.com/")
        or source.startswith("https://music.youtube.com/")
    ):
        return "YouTube"
    else:
        raise ValueError(f"Unsupported url: {input}")


async def _load_transcript(
    source: str | Transcript,
) -> Transcript:
    if isinstance(source, Transcript):
        return source

    platform = _platform(source)

    if not is_transcript_platform(platform):
        raise ValueError(f"Expected a valid link to {', '.join(TRANSCRIPT_PLATFORMS)}")

    match platform:
        case "Google":
            return gdocs.load(source)
        case "Notion":
            return await notion.load(source)
        case x:
            assert_never(x)


async def _save(request: SaveRequest) -> SaveResponse:
    match request.platform:
        case "Notion":
            if request.location is None:
                raise ValueError("For Notion `location` should be set to Database ID.")
            _, url, _ = await notion.create(
                request.transcript, format=request.format, database_id=request.location
            )
            return SaveResponse(url=url)
        case "Google":
            return SaveResponse(
                url=gdocs.create(request.transcript, format=request.format)
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
        case "Machine A" | "Machine B" | "Machine C" | "Machine D":
            raise ValueError(f"Unsupported method: {request.method}")
        case x:
            assert_never(x)


async def _synthesize(
    request: SynthesizeRequest, session: aiohttp.ClientSession
) -> Transcript:
    transcript = await _load_transcript(request.transcript)

    with TemporaryDirectory() as tmp_dir:
        synth_file, _, spans = await speech.synthesize_events(
            events=transcript.events,
            lang=transcript.lang,
            output_dir=tmp_dir,
        )

        if transcript.audio:
            audio_file = await obj.get(
                obj.storage_url(transcript.audio), dst_dir=tmp_dir
            )
            mono_audio = await media_ops.multi_channel_audio_to_mono(
                audio_file, output_dir=tmp_dir
            )
            match transcript.settings.space_between_events:
                case "Fill" | "Crop":
                    # has side effects :(
                    synth_file = await media_ops.mix(
                        files=(mono_audio, synth_file),
                        weights=(transcript.settings.original_audio_level, 10),
                        output_dir=tmp_dir,
                    )
                    if transcript.settings.space_between_events == "Crop":
                        synth_file = await media_ops.keep_events(
                            file=synth_file,
                            spans=spans,
                            output_dir=tmp_dir,
                            mode="audio",
                        )
                case "Blank":
                    synth_stream = media_ops.mix_spans(
                        original=mono_audio,
                        synth_file=synth_file,
                        spans=spans,
                        weights=(transcript.settings.original_audio_level, 10),
                    )
                    synth_file = await media_ops.write_streams(
                        streams=[synth_stream], output_dir=tmp_dir, extension="wav"
                    )
                    # writes only here ^
        with open(synth_file, "rb") as file:
            audio_url = (await _ingest(file, str(synth_file), session)).audio

        video_url = None
        if transcript.video:
            video_file = await obj.get(
                obj.storage_url(transcript.video), dst_dir=tmp_dir
            )

            if transcript.settings.space_between_events == "Crop":
                video_file = str(
                    await media_ops.keep_events(
                        file=video_file, spans=spans, output_dir=tmp_dir, mode="both"
                    )
                )

            dub_file = await media_ops.dub(
                video=video_file, audio=synth_file, output_dir=tmp_dir
            )

            with open(dub_file, "rb") as file:
                video_url = (await _ingest(file, str(dub_file), session)).video

    return replace(transcript, video=video_url, audio=audio_url)


async def _load(
    request: LoadRequest,
    stream: BinaryIO | None,
    session: aiohttp.ClientSession,
) -> Transcript:
    source = request.source or stream
    if source is None:
        raise ValueError("Either source or stream should be set.")

    platform = _platform(source)

    if is_transcript_platform(platform):
        if isinstance(source, BinaryIO):
            raise ValueError("Can't load transcript from stream")
        return await _load_transcript(source)
    else:
        if request.lang is None:
            raise ValueError("Language is not set")
        return await _transcribe(source, request.lang, request.method, session)


async def _transcribe(
    source: str | BinaryIO,
    lang: Language,
    method: Method,
    session: aiohttp.ClientSession,
) -> Transcript:

    asset = await _ingest(
        source=source,
        filename=None,
        session=session,
    )

    if not asset.audio:
        raise ValueError(f"No audio stream: {source}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_file = await obj.get(obj.storage_url(asset.audio), tmp_dir)
        output_mono = await media_ops.multi_channel_audio_to_mono(audio_file, tmp_dir)
        with open(output_mono, "rb") as file:
            task = await media.ingest(file, filename=str(output_mono), session=session)
            result = await tasks.future(task, session)
            if isinstance(result, Error):
                raise RuntimeError(result.message)
            assert result.audio is not None

    match method:
        case "Machine A" | "Machine B" | "Machine C":
            provider: ServiceProvider
            model: TranscriptionModel
            match method:
                case "Machine A":
                    provider = "Google"
                    model = "latest_long"
                case "Machine B":
                    provider = "Deepgram"
                    model = "default"
                case "Machine C":
                    provider = "Azure"
                    model = "default"
                case "Machine D":
                    provider = "Azure"
                    model = "azure_granular"
                case never:
                    assert_never(never)
            events = await speech.transcribe(
                uri=obj.storage_url(result.audio),
                lang=lang,
                model=model,
                provider=provider,
            )
        case "Subtitles":
            if isinstance(source, BinaryIO):
                raise ValueError("Can't load subtitles from stream")
            events = youtube.get_captions(source, lang=lang)
        case x:
            assert_never(x)

    events = speech.normalize_speech(
        events, gap_ms=GAP_MS, length=PHRASE_LENGTH, method="break_ends_sentence"
    )

    return Transcript(
        title=asset.meta.title if asset.meta else None,
        events=events,
        lang=lang,
        audio=asset.audio,
        video=asset.video,
        settings=Settings(),
    )


async def _ingest(
    source: str | BinaryIO | aiohttp.StreamReader | asyncio.StreamReader,
    filename: str | None,
    session: aiohttp.ClientSession,
) -> IngestResponse:
    response = await media.ingest(source=source, filename=filename, session=session)
    result = await tasks.future(response, session)
    if isinstance(result, Error):
        raise RuntimeError(result.message)

    return result


async def _translate(request: TranslateRequest):
    transcript = await _load_transcript(request.transcript)

    target_language = request.lang
    translated_events = language.translate_events(
        transcript.events, transcript.lang, target_language
    )
    translated = replace(
        transcript,
        events=translated_events,
        lang=target_language,
    )
    return translated


@routes.post("/transcript/translate")
async def translate(web_request: web.Request) -> web.Response:
    params = await web_request.json()
    try:
        response = await _translate(request=TranslateRequest(**params))
        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        raise errors.input_error(Error(message=str(e)))


@routes.post("/transcript/synthesize")
async def synthesize(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        response = await _synthesize(
            request=SynthesizeRequest(**params), session=client.create()
        )
        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        raise errors.input_error(Error(message=str(e)))


@routes.post("/transcript/save")
async def save(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        response = await _save(request=SaveRequest(**params))
        return web.json_response(pydantic_encoder(response))
    except (ValidationError, ValueError) as e:
        raise errors.input_error(Error(message=str(e)))


@routes.post("/transcript/load")
async def load(web_request: web.Request) -> web.Response:
    params = await web_request.json()

    try:
        request = LoadRequest(**params)
        if request.source is None:
            raise ValueError("request.source can't be null")

        if request.source.startswith("gs://"):
            with obj.stream(request.source, "r") as stream:
                response = await _load(
                    request=LoadRequest(**params),
                    stream=stream,
                    session=client.create(),
                )
        else:
            response = await _load(
                request=LoadRequest(**params),
                stream=None,
                session=client.create(),
            )

    except (ValidationError, ValueError) as e:
        raise errors.input_error(Error(message=str(e)))

    return web.json_response(pydantic_encoder(response))
