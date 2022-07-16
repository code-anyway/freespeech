import json
import logging
from dataclasses import replace
from typing import Tuple

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.lib import language
from freespeech.types import (
    Error,
    Job,
    Language,
    Media,
    Message,
    Source,
    Transcript,
    assert_never,
)

logger = logging.getLogger(__name__)


AudioVideoUrls = Tuple[str, str]


async def upload(*, session: aiohttp.ClientSession, url: str) -> Job[Media] | Error:
    params = {
        "url": url,
    }

    async with session.post("/upload", json=params) as resp:
        result = await resp.json()

        if resp.ok:
            return Job[Media](**result)
        else:
            return Error(**result)


async def media(*, session: aiohttp.ClientSession, url: str) -> Media | Error:
    params = {
        "url": url,
    }

    # astaff: Sasha, do we want to make it a GET?..\
    # this will remove boilerplate
    # with seriaizing/deserializing signle argument as dict
    async with session.post("/media", json=params) as resp:
        result = await resp.json()

        if resp.ok:
            return Media(**result)
        else:
            return Error(**result)


def subtitles(*, url: str, lang: Language) -> Transcript:
    raise NotImplementedError()


async def synth(
    *,
    session: aiohttp.ClientSession,
    transcript: Transcript,
) -> Job[Media] | Error:
    text = json.dumps(transcript, default=pydantic_encoder)

    async with session.post("/dub", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job[Media](**result)
        else:
            return Error(**result)


async def translate(
    *, session: aiohttp.ClientSession, transcript: Transcript, lang: Language
) -> Job[Transcript] | Error:
    events = language.translate_events(
        transcript.events,
        source=transcript.lang,
        target=lang,
    )

    transcript = replace(
        transcript, lang=lang, title=f"{transcript.title} ({lang})", events=events
    )

    return Job[Transcript](
        op="Translate",
        result=transcript,
        state="Successful",
        message=None,
        id=None,
    )


async def transcript(
    *, session: aiohttp.ClientSession, origin: Source, lang: Language
) -> Job[Transcript] | Error:
    match origin.method:
        case "Subtitles":
            return Job[Transcript](
                op="Transcribe",
                result=subtitles(url=origin.url, lang=lang),
                state="Successful",
                message=None,
                id=None,
            )
        case "Translate":
            raise NotImplementedError("Unsupported origin.method: 'Translate'")
        case "C3PO" | "R2D2" | "BB8":
            text = json.dumps(
                {"origin": origin, "lang": lang}, default=pydantic_encoder
            )
            async with session.post("/transcribe", text=text) as resp:
                result = await resp.json()

                if resp.ok:
                    return Job[Transcript](**result)
                else:
                    return Error(**result)
        case never:
            assert_never(never)


async def ask(
    *, session: aiohttp.ClientSession, request: Message
) -> Job[Transcript] | Job[Media] | Error:
    text = json.dumps(request, default=pydantic_encoder)

    async with session.post("/ask", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            match result["intent"]:
                case "Translate" | "Transcribe":
                    return Job[Transcript](**result)
                case "Synth":
                    return Job[Media](**result)
                case intent:
                    raise NotImplementedError(
                        f"Don't know how to handle intent: {intent}"
                    )
        else:
            return Error(**result)
