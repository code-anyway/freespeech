import json
import logging
from dataclasses import replace
from typing import BinaryIO, Sequence

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.lib import language
from freespeech.types import (
    Error,
    Job,
    Language,
    Media,
    Message,
    Method,
    Transcript,
    TranscriptReuqest,
)

logger = logging.getLogger(__name__)


async def ingest(
    *, source: str | BinaryIO, session: aiohttp.ClientSession
) -> Job | Error:
    params = {
        "url": source,
    }

    async with session.post("/ingest", json=params) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)


async def media(
    *, url: str, session: aiohttp.ClientSession
) -> Sequence[Media] | Error:
    params = {
        "url": url,
    }

    # astaff: Sasha, do we want to make it a GET?..\
    # this will remove boilerplate
    # with seriaizing/deserializing signle argument as dict
    async with session.post("/media", json=params) as resp:
        result = await resp.json()

        if resp.ok:
            return [Media(**record) for record in result]
        else:
            return Error(**result)


async def synthesize(
    *,
    transcript: Transcript,
    session: aiohttp.ClientSession,
) -> Job[Media] | Error:
    text = json.dumps(transcript, default=pydantic_encoder)

    async with session.post("/synthesize", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)


async def translate(
    transcript: Transcript,
    *,
    lang: Language,
    session: aiohttp.ClientSession
) -> Job[Transcript] | Error:
    events = language.translate_events(
        transcript.events,
        source=transcript.lang,
        target=lang,
    )

    transcript = replace(
        transcript, lang=lang, title=f"{transcript.title} ({lang})", events=events
    )

    return Job(
        op="Translate",
        state="Done",
        message=None,
        id=None,
    )


async def load(
    *,
    source: str,  # This can also be BinaryIO
    method: Method,
    lang: Language,
    session: aiohttp.ClientSession,
) -> Job | Error:
    text = json.dumps(
        TranscriptReuqest(url=source, method=method, lang=lang),
        default=pydantic_encoder,
    )
    async with session.post("/transcript", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)


async def ask(*, request: Message, session: aiohttp.ClientSession) -> Job | Error:
    text = json.dumps(request, default=pydantic_encoder)

    async with session.post("/ask", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)


from freespeech import media, transcript

t = transcript.load(source="https://youtube", method="C3PO", lang="en-US")
t = transcript.load(source="https://gdocs", method="Google")
t = transcript.load(source="https://notion", method="Notion")
t = transcript.load(source="https://youtube", method="Subtitles")
t = transcript.load(source="https://gdocs", method="SRT")


t_ru = transcript.translate(t, lang="ru-RU")

transcript.synthesize(t_ru)