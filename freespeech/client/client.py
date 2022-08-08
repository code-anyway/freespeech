import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Awaitable, BinaryIO, Dict

import aiohttp

from freespeech import env
from freespeech.lib.storage import obj

BUFFER_SIZE = 65535


def create(
    api_key: str | None = None,
    *,
    headers: Dict[str, str] | None = None,
    url: str = "https://api.freespeechnow.ai",
    timeout_sec: int = 1_800,
) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    headers = headers or {}
    headers = {**headers, "Authorization": f"Bearer {api_key}"}
    return aiohttp.ClientSession(base_url=url, timeout=timeout, headers=headers)


async def _read_chunk(
    stream: aiohttp.StreamReader | asyncio.StreamReader | BinaryIO,
) -> bytes:
    result = stream.read(BUFFER_SIZE)
    if isinstance(result, Awaitable):
        return await result
    else:
        return result


async def save_stream_to_blob(
    filename: str, stream: aiohttp.StreamReader | asyncio.StreamReader | BinaryIO
) -> str:
    filename = f"{str(uuid.uuid4())}{Path(filename).suffix}"
    blob_url = f"{env.get_storage_url()}/blobs/{filename}"

    with tempfile.TemporaryDirectory() as temp_dir:
        video_file = Path(temp_dir) / filename
        with open(video_file, "wb") as file:
            while chunk := await _read_chunk(stream):
                file.write(chunk)
        await obj.put(video_file, blob_url)

    return blob_url
