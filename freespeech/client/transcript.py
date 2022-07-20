from typing import Awaitable

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client import tasks
from freespeech.types import (
    Error,
    Language,
    Method,
    SynthesizeRequest,
    Task,
    Transcript,
    TranscriptReuqest,
    TranslateRequest,
)


async def load(
    source: str,  # This can also be BinaryIO
    *,
    method: Method,
    lang: Language | None,
    session: aiohttp.ClientSession,
) -> Awaitable[Transcript | Error] | Error:
    request = TranscriptReuqest(source=source, method=method, lang=lang)

    async with session.post("/transcript", json=pydantic_encoder(request)) as resp:
        result = await resp.json()

        if resp.ok:
            return tasks.future(Task(**result), return_type=Transcript)
        else:
            return Error(**result)


async def synthesize(
    transcript: Transcript,
    *,
    session: aiohttp.ClientSession,
) -> Awaitable[Transcript | Error] | Error:
    request = SynthesizeRequest(transcript=transcript)

    async with session.post("/synthesize", json=pydantic_encoder(request)) as resp:
        result = await resp.json()

        if resp.ok:
            return tasks.future(Task(**result), return_type=Transcript)
        else:
            return Error(**result)


async def translate(
    transcript: Transcript, *, lang: Language, session: aiohttp.ClientSession
) -> Awaitable[Transcript | Error] | Error:
    request = TranslateRequest(transcript=transcript, lang=lang)

    async with session.post("/translate", json=pydantic_encoder(request)) as resp:
        result = await resp.json()

        if resp.ok:
            return tasks.future(Task(**result), return_type=Transcript)
        else:
            return Error(**result)
