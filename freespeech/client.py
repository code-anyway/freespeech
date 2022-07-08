import logging
from dataclasses import asdict
from typing import Dict, Sequence, Tuple

import aiohttp.client
from aiohttp import ClientResponseError

from freespeech.types import Audio, Character, Clip, Event, Language, Meta

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


def _build_clip(clip_dict: Dict) -> Clip:
    meta_dict = clip_dict["meta"]
    meta = Meta(
        title=meta_dict["title"],
        description=meta_dict["description"],
        tags=meta_dict["tags"],
    )
    transcript = [Event(**event) for event in clip_dict["transcript"]]

    audio_url, audio_dict = clip_dict["audio"]
    audio = Audio(**audio_dict)

    clip = Clip(
        origin=clip_dict["origin"],
        lang=clip_dict["lang"],
        audio=(audio_url, audio),
        video=clip_dict.get("video", None),
        transcript=transcript,
        meta=meta,
        parent_id=clip_dict["parent_id"],
        _id=clip_dict["_id"],
        last_updated=clip_dict["last_updated"],
    )

    return clip


async def upload(http_client: aiohttp.ClientSession, video_url: str, lang: str) -> Clip:
    params = {
        "url": video_url,
        "lang": lang,
    }

    async with http_client.post("/clips/upload", json=params) as resp:
        await _raise_if_error(resp)
        clip_dict = await resp.json()

    return _build_clip(clip_dict)


async def clip(http_client: aiohttp.ClientSession, clip_id: str) -> Clip:
    async with http_client.get(f"/clips/{clip_id}") as resp:
        await _raise_if_error(resp)
        clip_dict = await resp.json()

    return _build_clip(clip_dict)


async def dub(
    http_client: aiohttp.ClientSession,
    clip_id: str,
    transcript: Sequence[Event],
    default_character: Character,
    lang: Language,
    pitch: float,
    weights: Tuple[int, int],
) -> Clip:
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
        return _build_clip(clip_dict)


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
