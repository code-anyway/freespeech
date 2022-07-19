import json

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.types import (
    Error,
    Job,
    Language,
    Media,
    Method,
    Transcript,
    TranscriptReuqest,
    TranslateRequest,
)


async def load(
    *,
    source: str,  # This can also be BinaryIO
    method: Method,
    lang: Language,
    session: aiohttp.ClientSession,
) -> Job[Transcript] | Error:
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


async def synthesize(
    transcript: Transcript,
    *,
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
    transcript: Transcript, *, lang: Language, session: aiohttp.ClientSession
) -> Job[Transcript] | Error:
    text = json.dumps(
        TranslateRequest(transcript=transcript, lang=lang), default=pydantic_encoder
    )

    async with session.post("/translate", text=text) as resp:
        result = await resp.json()

        if resp.ok:
            return Job(**result)
        else:
            return Error(**result)
