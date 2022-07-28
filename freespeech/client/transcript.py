import asyncio
import json
from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.tasks import Task
from freespeech.lib import hash
from freespeech.types import (
    Error,
    Language,
    LoadRequest,
    Method,
    SaveRequest,
    SaveResponse,
    SynthesizeRequest,
    Transcript,
    TranslateRequest,
)


async def load(
    source: str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
    *,
    method: Method,
    lang: Language,
    session: aiohttp.ClientSession,
) -> Task[Transcript] | Error:
    """Load transcript.

    Loads transcript from `source` using `method` and `lang` (language).

    Args:
        source (str | aiohttp.StreamReader | asyncio.StreamReader | BinaryIO):
            Transcript source. Can be a url or a stream.
        method (str): How to extract the Transcript from url.

            Machine-based transcription:

            - `"Machine A"`.
            - `"Machine B"`.
            - `"Machine C"`.

            Subtitles:

            - `"Subtitles"` — extract from the video container.
            - `"SRT"` — popular subtitle format.
            - `"SSMD"` — freespeech's speech synthesis markdown.

            Document platforms:

            - `"Google"` — Google Docs.
            - `"Notion"` — Notion.
        lang (str): A BCP 47 tag indicating language of a transcript.

            Supported values:

            - `"en-US"` (English).
            - `"uk-UA"` (Ukrainian).
            - `"ru-RU"` (Russian).
            - `"pt-PT"` (Portuguese).
            - `"es-US"` (Spanish).
            - `"de-DE"` (German).
    Returns:
        Task[Transcript] or Error: A Task that is expected
        to return Transcript or Error if operation was unsuccessful.

    Examples:
    ```python
    from freespeech.client import client, transcript, tasks


    session = client.create(key="your-api-token")
    task = await transcript.load(
                source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
                method="Subtitles",
                lang="en-US",
                session=session,
            )
    result = await tasks.future(task)
    ```
    """
    url = source if isinstance(source, str) else None
    request = LoadRequest(source=url, method=method, lang=lang)

    async def _future() -> Transcript | Error:
        with aiohttp.MultipartWriter("form-data") as writer:
            writer.append_json(pydantic_encoder(request))

            if not request.source:
                writer.append(source)

            async with session.post("/load", data=writer) as resp:
                result = await resp.json()

                if resp.ok:
                    return Transcript(**result)
                else:
                    return Error(**result)

    return Task[Transcript](
        state="Running",
        op="Transcribe",
        id=hash.string(json.dumps(pydantic_encoder(request))),
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


async def save(
    transcript: Transcript,
    *,
    method: Method,
    location: str | None,
    session: aiohttp.ClientSession,
) -> SaveResponse | Error:
    request = SaveRequest(transcript=transcript, location=location, method=method)
    async with session.post("/save", json=pydantic_encoder(request)) as resp:
        result = await resp.json()
        if resp.ok:
            return SaveResponse(**result)
        else:
            return Error(**result)
