from dataclasses import replace
from datetime import datetime, timezone
import pytest
from freespeech import client
from freespeech.api import crud, dub

from freespeech.lib import language, notion, speech

from aiohttp import web

from freespeech.types import Character, Language, url


TRANSCRIPT_DATABASE_ID = "da8013c44f6f4809b3e7ed53dfbfb461"

# https://www.youtube.com/watch?v=tZ27pVGFVJ4

# TRANSCRIPT_TITLE = "Humans Need Not Apply"
# ORIGIN = "https://www.youtube.com/watch?v=7Pq-S557XQU"
# LANG = "ru-RU"
# TRANSCRIPT_SOURCE = "Subtitles"
# VOICE = "Grace Hopper"

TRANSCRIPT_TITLE = (
    "Звернення Президента України Володимира Зеленського за підсумками 62-го дня війни"
)
ORIGIN = "https://www.youtube.com/watch?v=tZ27pVGFVJ4"
LANG = "uk-UK"
TRANSCRIPT_SOURCE = "Subtitles"
VOICE = "Alan Turing"


async def _dub(dub_http_client, crud_http_client, page_id) -> notion.Transcript:
    transcript = await notion.get_transcript(page_id)
    dubbed_clip = await client.dub(
        http_client=dub_http_client,
        clip_id=transcript.clip_id,
        transcript=transcript.events,
        default_character=transcript.voice.character,
        lang=transcript.lang,
        pitch=transcript.voice.pitch,
        weights=transcript.weights,
    )
    public_url = await client.video(crud_http_client, dubbed_clip._id)
    updated_transcript = replace(
        transcript,
        dub_url=public_url,
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
    return await notion.put_transcript(TRANSCRIPT_DATABASE_ID, updated_transcript)


async def _new_page(title: str, origin: url, lang: Language, source: notion.Source, voice: Character) -> notion.Transcript:
    properties = {
        "Name": {"title": [{"type": "text", "text": {"content": title}}]},
        "Origin": {"url": origin},
        "Speak In": {"select": {"name": lang}},
        "Transcript Source": {"select": {"name": source}},
        "Voice": {"select": {"name": voice}},
    }

    page = await notion.create_page(TRANSCRIPT_DATABASE_ID, properties, blocks=[])

    return await notion.get_transcript(page["id"])


@pytest.mark.asyncio
async def test_subtitles(aiohttp_client):
    page_id = "c013589eb1af41e0a92b775ce4025186"
    # https://www.notion.so/62-a48cc4eb64b14c379b11c91dae2d069e
    # page_id = "a48cc4eb64b14c379b11c91dae2d069e"
    transcript = await notion.get_transcript(page_id)

    # TODO (astaff): I think ultimately an e2e test should be using
    # the CLI to init the routes. Leaving it as is for now as this will
    # require a modification of how CLI is initialized. I would assume we should
    # pass a test client somehow...
    crud_service = web.Application()
    crud_service.add_routes(crud.routes)
    crud_http_client = await aiohttp_client(crud_service)

    clip = await client.upload(
        http_client=crud_http_client,
        video_url=transcript.origin,
        lang=transcript.lang,
    )

    transcript = await notion.put_transcript(
        database_id=TRANSCRIPT_DATABASE_ID,
        transcript=replace(
            transcript,
            events=speech.normalize_speech(clip.transcript),
            clip_id=clip._id,
            meta=replace(clip.meta, description=clip.meta.description),
        ),
    )


@pytest.mark.asyncio
async def test_translate():
    page_id = "3e7e4e5345c94d8f87fc7ba06595c35e"

    transcript = await notion.get_transcript(page_id)
    transcript_from = await notion.get_transcript(transcript.source)
    events = language.translate_events(
        transcript_from.events, source=transcript_from.lang, target=transcript.lang
    )

    transcript_translated = replace(transcript, events=events)
    transcript_translated = await notion.put_transcript(
        TRANSCRIPT_DATABASE_ID, transcript_translated
    )


@pytest.mark.asyncio
async def test_dub(aiohttp_client):
    # page_id = "3e7e4e5345c94d8f87fc7ba06595c35e"  # Zelensky
    page_id = "c013589eb1af41e0a92b775ce4025186"  # CGP Grey
    crud_service = web.Application()
    crud_service.add_routes(crud.routes)
    crud_http_client = await aiohttp_client(crud_service)

    dub_service = web.Application()
    dub_service.add_routes(dub.routes)
    dub_http_client = await aiohttp_client(dub_service)

    await _dub(dub_http_client=dub_http_client, crud_http_client=crud_http_client, page_id=page_id)
