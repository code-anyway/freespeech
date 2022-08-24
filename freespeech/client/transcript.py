import asyncio
from typing import BinaryIO

import aiohttp
from pydantic.json import pydantic_encoder

from freespeech.client.client import save_stream_to_blob
from freespeech.client.tasks import Task
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
    lang: Language | None,
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
    if not isinstance(source, str):
        source = await save_stream_to_blob("", source)
    request = LoadRequest(source=source, method=method, lang=lang)

    with aiohttp.MultipartWriter("form-data") as writer:
        writer.append_json(pydantic_encoder(request))

        async with session.post("/api/transcript/load", data=writer) as resp:
            result = await resp.json()

            if resp.ok:
                return Task[Transcript](**result)
            else:
                print("bruuuh")
                print(result)
                return Error(**result)


async def synthesize(
    transcript: Transcript | str,
    *,
    session: aiohttp.ClientSession,
) -> Task[Transcript] | Error:
    request = SynthesizeRequest(transcript=transcript)

    async with session.post(
        "/api/transcript/synthesize", json=pydantic_encoder(request)
    ) as resp:
        result = await resp.json()
        if resp.ok:
            return Task[Transcript](**result)
        else:
            return Error(**result)


async def translate(
    transcript: Transcript | str, *, lang: Language, session: aiohttp.ClientSession
) -> Task[Transcript] | Error:
    request = TranslateRequest(transcript=transcript, lang=lang)

    async with session.post(
        "/api/transcript/translate", json=pydantic_encoder(request)
    ) as resp:
        result = await resp.json()
        if resp.ok:
            return Task[Transcript](**result)
        else:
            return Error(**result)


async def save(
    transcript: Transcript,
    *,
    method: Method,
    location: str | None,
    session: aiohttp.ClientSession,
) -> Task[SaveResponse] | Error:
    request = SaveRequest(transcript=transcript, location=location, method=method)
    async with session.post(
        "/api/transcript/save", json=pydantic_encoder(request)
    ) as resp:
        result = await resp.json()
        if resp.ok:
            return Task[SaveResponse](**result)
        else:
            return Error(**result)
