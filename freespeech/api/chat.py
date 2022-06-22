from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Sequence, Tuple

import aiohttp
from aiohttp import web

from freespeech import client, env
from freespeech.lib import language, media, notion, speech
from freespeech.lib.storage import obj
from freespeech.types import (
    Audio,
    Event,
    Language,
    ServiceProvider,
    Voice,
    assert_never,
    is_language,
    url,
)

routes = web.RouteTableDef()

DUB_CLIENT_TIMEOUT = 3600
CRUD_CLIENT_TIMEOUT = 3600

# Events with the gap greater than GAP_MS won't be contatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600

# For now, hardcode it to https://www.notion.so/f27eb91e04754fbcb6ace5f9871e7bb0?v=d7d74a5fe6c644d39b5ccc714efa11a6  # noqa: E501
# TODO: remove once we have users, sessions and stuff.
NOTION_DATABASE_ID = "f27eb91e04754fbcb6ace5f9871e7bb0"


def normalize_speech(
    events: Sequence[Event], method: speech.Normalization
) -> Sequence[Event]:
    return speech.normalize_speech(
        events, gap_ms=GAP_MS, length=PHRASE_LENGTH, method=method
    )


@routes.post("/say")
async def say(request):
    params = await request.json()

    text = params["text"]
    state = params.get("state", {})

    intent, entities = await language.intent(text)
    state = {**state, **entities}

    match (intent):
        case "transcribe":
            origin, lang, method = get_transcribe_arguments(state)
            document_url = await transcribe(origin[0], lang[0], method[0])

            return web.json_response(
                {"text": f"Here you are: {document_url}", "url": document_url}
            )
        case "translate":
            pass
        case "dub":
            pass
        case never:
            assert_never(never)


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


def get_transcribe_arguments(state: Dict[str, Any]) -> Tuple[str, Language, Source]:
    origin = state.get("url", None)
    if not origin:
        raise AttributeError("Missing origin url")

    lang = state.get("language", None)
    if not lang:
        raise AttributeError("Missing language")
    is_language(lang)

    method = state.get("method", None)
    if not method:
        raise AttributeError("Missing method")
    notion.is_source(method)

    return origin, lang, method

async def transcribe(origin: url, lang: Language, method: notion.Source) -> url:
    async with get_crud_client() as _client:
        clip = await client.upload(
            http_client=_client,
            video_url=origin,
            lang=lang,
        )

    match (method):
        case "Subtitles":
            transcript = clip.transcript
        case "Machine A" | "Machine B":
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

            transcript = await speech.transcribe(
                uri=uri, audio=audio, lang=lang, provider=provider
            )
        case _:
            raise ValueError(f"Unsupported method: {method}")

    properties = {
        notion.PROPERTY_NAME_PAGE_TITLE: {
            "title": [{"type": "text", "text": {"content": clip.meta.title}}],
        },
        notion.PROPERTY_NAME_LANG: {"select": {"name": lang[0]}},
        notion.PROPERTY_NAME_ORIGIN: {"url": origin[0]},
        notion.PROPERTY_NAME_CLIP_ID: notion.render_text(clip._id),
        notion.PROPERTY_NAME_SOURCE: {"select": {"name": method}},
        notion.PROPERTY_NAME_DESCRIPTION: notion.render_text(clip.meta.description),
        notion.PROPERTY_NAME_TITLE: notion.render_text(clip.meta.title),
        notion.PROPERTY_NAME_TAGS: {"multi_select": [{"name": tag} for tag in clip.meta.tags or []]},
    }
    blocks: List[dict] = sum([notion.render_event(e) for e in transcript], [])

    res = await notion.create_page(
        database_id=NOTION_DATABASE_ID, properties=properties, blocks=blocks
    )

    return res["url"]


def dub(transcript: url, voice: Voice | None) -> url:
    pass


def translate(transcript: url, lang: Language) -> str:
    pass


# TODO (astaff): move outside of notion.py?
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
