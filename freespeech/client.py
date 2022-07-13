import logging
from dataclasses import asdict
from typing import Dict, Sequence, Tuple

import aiohttp.client
from aiohttp import ClientResponseError

from freespeech.types import Audio, Character, Event, Language, Meta, Video

logger = logging.getLogger(__name__)


async def _raise_if_error(resp) -> None:
    """Raise if error response, take details from body

    This function should be used instead of a standard `raise_for_status()` since
    we are passing exception details in response body rather than in HTTP response
    reason.
    """
    if resp.ok:
        return
    error_message = await resp.text()
    raise ClientResponseError(
        status=resp.status,
        request_info=resp.request_info,
        message=error_message,
        history=resp.history,
    )


async def upload(
    http_client: aiohttp.ClientSession, video_url: str, lang: str
) -> Audio | Video:
    params = {
        "url": video_url,
        "lang": lang,
    }

    async with http_client.post("/clips/upload", json=params) as resp:
        await _raise_if_error(resp)
        clip_dict = await resp.json()

    # TODO (astaff): initialize data structures for Audio or Video
    return None


async def clip(http_client: aiohttp.ClientSession, clip_id: str) -> Audio | Video:
    async with http_client.get(f"/clips/{clip_id}") as resp:
        await _raise_if_error(resp)
        clip_dict = await resp.json()

    # TODO (astaff): initialize data structures for Audio or Video
    return None


async def dub(
    http_client: aiohttp.ClientSession,
    clip_id: str,
    transcript: Sequence[Event],
    default_character: Character,
    lang: Language,
    pitch: float,
    weights: Tuple[int, int],
) -> Audio | Video:
    params = {
        "transcript": [asdict(e) for e in transcript],
        "characters": {"default": default_character},
        "lang": lang,
        "pitch": pitch,
        "weights": weights,
    }

    async with http_client.post(f"/clips/{clip_id}/dub", json=params) as resp:
        await _raise_if_error(resp)
        clip_dict = await resp.json()
        # TODO (astaff): initialize data structures for Audio or Video
        return None


async def video(http_client: aiohttp.ClientSession, clip_id: str) -> str:
    async with http_client.get(f"/clips/{clip_id}/video") as resp:
        await _raise_if_error(resp)
        video_dict = await resp.json()
    return video_dict["url"]


async def say(
    http_client: aiohttp.ClientSession, message: str
) -> Tuple[str, str, Dict]:
    # todo (lexaux) push state back to API
    async with http_client.post("/say", json={"text": message}) as resp:
        await _raise_if_error(resp)
        data = await resp.json()
        return data["text"], data["result"], data["state"]
