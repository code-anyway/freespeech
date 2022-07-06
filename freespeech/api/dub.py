import logging
from dataclasses import asdict, replace
from tempfile import TemporaryDirectory
from typing import List, Tuple

from aiohttp import web

from freespeech import env
from freespeech.lib import media, speech
from freespeech.lib.storage import doc, obj
from freespeech.types import Clip, Event, Language, Voice

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


@routes.post("/clips/{clip_id}/dub")
async def create_dub(request):
    clip_id = request.match_info["clip_id"]
    params = await request.json()

    voice = Voice(character=params["characters"]["default"], pitch=params["pitch"])
    events = [
        Event(
            time_ms=event["time_ms"],
            duration_ms=event["duration_ms"],
            chunks=event["chunks"],
            voice=Voice(**value) if (value := event.get("voice", None)) else None,
        )
        for event in params["transcript"]
    ]

    db = doc.google_firestore_client()
    clip = await doc.get(db, "clips", clip_id)
    clip = Clip(**clip)

    dub_clip = await _dub(
        clip=clip,
        lang=params["lang"],
        voice=voice,
        events=events,
        weights=params["weights"],
    )
    await doc.put(db, "clips", dub_clip._id, asdict(dub_clip))

    return web.json_response(asdict(dub_clip))


# TODO (astaff): this should go into API eventually.
async def _dub(
    clip: Clip,
    lang: Language,
    voice: Voice,
    events: List[Event],
    weights: Tuple[int, int],
) -> Clip:
    with TemporaryDirectory() as tmp_dir:
        if not clip.video:
            raise ValueError(f"Clip _id={clip._id} has no video.")

        synth_file, voices = await speech.synthesize_events(
            events=events,
            voice=voice.character,
            lang=lang,
            pitch=voice.pitch or 0.0,
            output_dir=tmp_dir,
        )
        original_weight, synth_weight = weights

        audio_url, _ = clip.audio
        audio_file = await obj.get(audio_url, tmp_dir)
        mixed_file = await media.mix(
            files=(audio_file, synth_file),
            weights=(original_weight, synth_weight),
            output_dir=tmp_dir,
        )

        video_url, _ = clip.video
        video_file = await obj.get(video_url, tmp_dir)
        dub_file = await media.dub(
            video=video_file, audio=mixed_file, output_dir=tmp_dir
        )

        ((dub_audio, *_), (dub_video, *_)) = media.probe(dub_file)
        dub_url = f"{env.get_storage_url()}/clips/{dub_file.name}"

        events_with_voices = [replace(e, voice=v) for e, v in zip(events, voices)]
        dub_clip = Clip(
            origin=clip.origin,
            lang=lang,
            audio=(dub_url, dub_audio),
            video=(dub_url, dub_video),
            transcript=events_with_voices,
            meta=clip.meta,
            parent_id=clip._id,
        )

        await obj.put(dub_file, dub_url)

        return dub_clip
