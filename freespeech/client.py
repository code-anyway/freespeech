from dataclasses import asdict
from typing import Dict, Sequence, Tuple

import aiohttp.client

from freespeech.types import Character, Clip, Event, Language, Meta


TIMEOUT = aiohttp.ClientTimeout(total=3600)


async def upload(service_url: str, video_url: str, lang: str) -> Clip:
    params = {
        "url": video_url,
        "lang": lang,
    }

    async with aiohttp.ClientSession(timeout=TIMEOUT) as client:
        async with client.post(f"{service_url}/clips/upload", json=params) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            clip_dict = await resp.json()

    clip = _build_clip(clip_dict)

    return clip


def _build_clip(clip_dict: Dict) -> Clip:
    meta_dict = clip_dict["meta"]
    meta = Meta(
        title=meta_dict["title"],
        description=meta_dict["description"],
        tags=meta_dict["tags"],
    )
    transcript = [Event(**event) for event in clip_dict["transcript"]]

    clip = Clip(
        origin=clip_dict["origin"],
        lang=clip_dict["lang"],
        audio=clip_dict["audio"],
        video=clip_dict.get("video", None),
        transcript=transcript,
        meta=meta,
        parent_id=clip_dict["parent_id"],
        _id=clip_dict["_id"],
        last_updated=clip_dict["last_updated"],
    )

    return clip


async def clip(service_url: str, clip_id: str) -> Clip:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as client:
        async with client.get(f"{service_url}/clips/{clip_id}") as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            clip_dict = await resp.json()

    clip = _build_clip(clip_dict)

    return clip


async def dub(
    service_url: str,
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

    async with aiohttp.ClientSession(timeout=TIMEOUT) as client:
        url = f"{service_url}/clips/{clip_id}/dub"
        async with client.post(url=url, json=params) as resp:
            assert resp.status == 200
            clip_dict = await resp.json()

    return _build_clip(clip_dict)


async def video(service_url: str, clip_id: str) -> str:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as client:
        url = f"{service_url}/clips/{clip_id}/video"
        resp = await client.get(url)
        if resp.status != 200:
            raise RuntimeError(await resp.text())
        video_dict = await resp.json()
    return video_dict["url"]
