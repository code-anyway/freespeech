import logging
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any, Dict, Sequence, Tuple

import aiohttp
from aiohttp import web

from freespeech import client, env
from freespeech.lib import gdocs, language, media, speech
from freespeech.lib.storage import obj
from freespeech.types import (
    Audio,
    Character,
    Event,
    Language,
    ServiceProvider,
    Source,
    assert_never,
    is_character,
    is_language,
    is_source,
    url,
)

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)

DUB_CLIENT_TIMEOUT = 3600
CRUD_CLIENT_TIMEOUT = 3600

# Events with the gap greater than GAP_MS won't be contatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600


def normalize_speech(
    events: Sequence[Event], method: speech.Normalization
) -> Sequence[Event]:
    return speech.normalize_speech(
        events, gap_ms=GAP_MS, length=PHRASE_LENGTH, method=method
    )


@routes.post("/say")
async def say(request):
    def _raise_unknown_query():
        raise aiohttp.web.HTTPBadRequest(
            reason=f"I don't know how to handle {intent}. Try /help?"
        )

    params = await request.json()

    text = params["text"]
    state = params.get("state", {})

    intent: str = ""
    try:
        intent, entities = await language.intent(text)
        state = {**state, **entities}
    except ValueError:
        _raise_unknown_query()

    match intent:
        case "transcribe":
            origin, lang, method = get_transcribe_arguments(state)
            document_url = await transcribe(origin, lang, method)
            return web.json_response(
                {
                    "text": f"Here you are: {document_url}",
                    "result": document_url,
                    "state": state,
                }
            )

        case "translate":
            document_url, lang = get_translate_arguments(state)
            translated_url = await translate(document_url, lang)
            return web.json_response(
                {
                    "text": f"Here you are: {translated_url}",
                    "result": translated_url,
                    "state": state,
                }
            )

        case "dub":
            document_url, voice = get_dub_arguments(state)
            video_url = await dub(document_url, voice=voice)
            return web.json_response(
                {
                    "text": f"Here you are: {video_url}",
                    "result": video_url,
                    "state": state,
                }
            )

        case _:
            _raise_unknown_query()


def get_dub_arguments(state: Dict[str, Any]) -> Tuple[url, Character | None]:
    document_url = get_page_url(state)
    voice = get_voice(state)

    return document_url, voice


def get_translate_arguments(state: Dict[str, Any]) -> Tuple[url, Language]:
    document_url = get_page_url(state)
    lang = get_language(state)

    return document_url, lang


def get_transcribe_arguments(state: Dict[str, Any]) -> Tuple[str, Language, Source]:
    origin = get_origin(state)
    lang = get_language(state)
    method = get_method(state)

    return origin, lang, method


def get_voice(state: Dict[str, Any]) -> Character | None:
    voice = state.get("voice", None)

    if voice is None:
        return None

    if len(voice) > 1:
        logger.warning(f"Multiple voices in the intent: {voice}")
    voice, *_ = voice

    if not is_character(voice):
        raise ValueError(
            f"Unsupported voice: {voice}. Try Alan Turing, Grace Hopper, Bill or Melinda."  # noqa: E501
        )

    return voice


def get_method(state: Dict[str, Any]) -> Source:
    method = state.get("method", None)
    if not method:
        raise AttributeError(
            "Missing transcript method. Try Machine A, Machine B, or Subtitles."
        )
    if len(method) > 1:
        logger.warning(f"Multiple transcription methods in the intent: {method}")
    method, *_ = method

    if not is_source(method):
        raise ValueError(
            f"Unsupported transcript method: {method}. Try Machine A, Machine B, or Subtitles."  # noqa: E501
        )

    return method


def get_language(state: Dict[str, Any]) -> Language:
    lang = state.get("language", None)
    if not lang:
        raise AttributeError("Missing language.")

    if len(lang) > 1:
        logger.warning(f"Multiple languages in the intent: {lang}")
    lang, *_ = lang

    if not is_language(lang):
        raise ValueError(f"Unsupported language: {lang}")
    return lang


def get_origin(state: Dict[str, Any]) -> str:
    origin = state.get("url", None)
    if not origin:
        raise AttributeError(
            "Missing origin url. Try something that starts with https://youtube.com"
        )
    if len(origin) > 1:
        logger.warning(f"Multiple origins in the intent: {origin}")
    origin, *_ = origin
    return origin


def get_page_url(state: Dict[str, Any]) -> str:
    page_url = state.get("url", None)
    if not page_url:
        raise AttributeError(
            "Missing document url. Try something that starts with https://docs.google.com/"  # noqa: E501
        )
    if len(page_url) > 1:
        logger.warning(f"Multiple documents in the intent: {page_url}")
    page_url, *_ = page_url
    return page_url


async def transcribe(origin: url, lang: Language, method: Source) -> url:
    async with get_crud_client() as _client:
        clip = await client.upload(
            http_client=_client,
            video_url=origin,
            lang=lang,
        )

    match (method):
        case "Subtitles":
            events = clip.transcript
        case "Machine" | "Machine A" | "Machine B" | "Machine C":
            uri, audio = await get_audio(clip._id)

            # TODO (astaff): move this to lib.transcribe
            provider: ServiceProvider
            match method:
                case "Machine A":
                    provider = "Google"
                case "Machine B":
                    provider = "Deepgram"
                case "Machine C":
                    provider = "Azure"

            events = await speech.transcribe(
                uri=uri, audio=audio, lang=lang, provider=provider
            )
        case "Translate":
            raise ValueError(f"Unsupported transcription method: {method}")
        case never:
            assert_never(never)

    events = normalize_speech(events, method="break_ends_sentence")

    title = f"{clip.meta.title} ({lang})"

    async with get_crud_client() as _client:
        video_url = await client.video(_client, clip._id)

    page = gdocs.Page(
        origin=origin,
        language=lang,
        voice="Alan Turing",
        clip_id=clip._id,
        method=method,
        original_audio_level=2,
        video=video_url,
    )

    doc_url = gdocs.create(title, page=page, events=events)

    return doc_url


async def dub(transcript: url, voice: Character | None) -> url:
    page, events = gdocs.parse(gdocs.extract(transcript))

    async with get_crud_client() as _client:
        clip = await client.clip(_client, page.clip_id)

    async with get_dub_client() as _client:
        dubbed_clip = await client.dub(
            http_client=_client,
            clip_id=clip._id,
            transcript=events,
            default_character=voice or page.voice,
            lang=page.language,
            pitch=0.0,
            weights=(page.original_audio_level, 10),
        )

    async with get_crud_client() as _client:
        public_url = await client.video(_client, dubbed_clip._id)

    return public_url


async def translate(transcript: url, lang: Language) -> str:
    page, events = gdocs.parse(gdocs.extract(transcript))
    events = language.translate_events(
        events,
        source=page.language,
        target=lang,
    )

    page = replace(page, language=lang)
    async with get_crud_client() as _client:
        clip = await client.clip(_client, page.clip_id)

    title = f"{clip.meta.title} ({lang})"
    doc_url = gdocs.create(title, page=page, events=events)

    return doc_url


def get_dub_client():
    return aiohttp.ClientSession(
        base_url=env.get_dub_service_url(),
        timeout=aiohttp.ClientTimeout(DUB_CLIENT_TIMEOUT),
    )


def get_crud_client():
    return aiohttp.ClientSession(
        base_url=env.get_crud_service_url(),
        timeout=aiohttp.ClientTimeout(CRUD_CLIENT_TIMEOUT),
    )


async def get_audio(clip_id: str) -> Tuple[str, Audio]:
    async with get_crud_client() as _client:
        clip = await client.clip(_client, clip_id)

    audio_url, _ = clip.audio

    with TemporaryDirectory() as tmp_dir:
        audio_file = await obj.get(audio_url, tmp_dir)
        mono_file = await media.multi_channel_audio_to_mono(audio_file, tmp_dir)
        ((audio_info, *_), _) = media.probe(mono_file)
        output_url = f"{env.get_storage_url()}/transcribe/{mono_file.name}"
        await obj.put(mono_file, output_url)

    return output_url, audio_info
