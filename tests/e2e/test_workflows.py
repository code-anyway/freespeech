import pytest
from aiohttp import web

from freespeech.api import crud, dub, notion
# from freespeech.lib import notion
# from freespeech.types import Character, Language, url

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


# async def _new_page(
# title: str, origin: url, lang: Language, source: notion.Source, voice: Character
# ) -> notion.Transcript:
#     properties = {
#         "Name": {"title": [{"type": "text", "text": {"content": title}}]},
#         "Origin": {"url": origin},
#         "Speak In": {"select": {"name": lang}},
#         "Transcript Source": {"select": {"name": source}},
#         "Voice": {"select": {"name": voice}},
#     }

#     page = await notion.create_page(TRANSCRIPT_DATABASE_ID, properties, blocks=[])

#     return await notion.get_transcript(page["id"])


@pytest.mark.asyncio
async def test_notion(aiohttp_client, aiohttp_server, monkeypatch):
    app = web.Application()
    app.add_routes(crud.routes)
    app.add_routes(dub.routes)
    _ = await aiohttp_server(app, port=8088)

    app = web.Application()
    app.add_routes(notion.routes)
    client = await aiohttp_client(app)

    monkeypatch.setenv("FREESPEECH_CRUD_SERVICE_URL", "http://localhost:8088")
    monkeypatch.setenv("FREESPEECH_DUB_SERVICE_URL", "http://localhost:8088")

    params = {}
    resp = await client.post(f"/notion/{TRANSCRIPT_DATABASE_ID}/process", json=params)

    transcripts = await resp.json()

    assert transcripts == {}
