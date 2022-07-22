import json

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.lib import hash
from freespeech.types import (
    Error,
    Language,
    Method,
    SynthesizeRequest,
    Transcript,
    LoadRequest,
    TranslateRequest,
)


async def load(
    source: str,  # This can also be BinaryIO
    *,
    method: Method,
    lang: Language | None,
    session: aiohttp.ClientSession,
) -> Task[Transcript] | Error:
    request = LoadRequest(source=source, method=method, lang=lang)

    async def _future() -> Transcript | Error:
        async with session.post("/transcript", json=pydantic_encoder(request)) as resp:
            result = await resp.json()

            if resp.ok:
                return Transcript(**result)
            else:
                return Error(**result)

    return Task[Transcript](
        state="Running",
        op="Transcribe",
        id=hash.string(json.dumps(request)),
        message="Estimated wait time: 10 minutes",
        _future=_future(),
    )


async def synthesize(
    transcript: Transcript,
    *,
    session: aiohttp.ClientSession,
) -> Task[Transcript] | Error:
    request = SynthesizeRequest(transcript=transcript)

    async def _future() -> Transcript | Error:
        async with session.post("/synthesize", json=pydantic_encoder(request)) as resp:
            result = await resp.json()
            if resp.ok:
                return Transcript(**result)
            else:
                return Error(**result)

    return Task[Transcript](
        state="Running",
        op="Synthesize",
        message="Estimated wait time: 5 minutes",
        id=hash.string(json.dumps(pydantic_encoder(request))),
        _future=_future(),
    )


async def translate(
    transcript: Transcript, *, lang: Language, session: aiohttp.ClientSession
) -> Task[Transcript] | Error:
    request = TranslateRequest(transcript=transcript, lang=lang)

    async def _future() -> Transcript | Error:
        async with session.post("/translate", json=pydantic_encoder(request)) as resp:
            result = await resp.json()
            if resp.ok:
                return Transcript(**result)
            else:
                return Error(**result)

    return Task[Transcript](
        state="Running",
        op="Translate",
        message="Estimated wait time: 2 minutes",
        id=hash.string(json.dumps(pydantic_encoder(request))),
        _future=_future(),
    )
