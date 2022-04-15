from tempfile import TemporaryDirectory
from freespeech import env
from aiohttp import web
from freespeech.types import Event, Clip
from freespeech.api.storage import doc, obj
from freespeech.api import speech, media
from dataclasses import asdict


routes = web.RouteTableDef()


@routes.post("/clips/{clip_id}/dub")
async def create_dub(request):
    clip_id = request.match_info["clip_id"]

    params = await request.json()

    transcript = params["transcript"]
    characters = params["characters"]
    lang = params["lang"]
    pitch = params["pitch"]
    original_weight, synth_weight = params["weights"]

    events = [Event(**event) for event in transcript]
    character = characters["default"]

    client = doc.google_firestore_client()
    clip = await doc.get(client, "clips", clip_id)
    clip = Clip(**clip)

    from pprint import pprint
    pprint(clip)

    with TemporaryDirectory() as tmp_dir:
        synth_file, voices = speech.synthesize_events(events=events,
                                                      voice=character,
                                                      lang=lang,
                                                      pitch=pitch,
                                                      output_dir=tmp_dir)
        audio_url, _ = clip.audio
        video_url, _ = clip.video

        audio_file = obj.get(audio_url, tmp_dir)
        mixed_file = media.mix([(audio_file, original_weight),
                                (synth_file, synth_weight)],
                               output_dir=tmp_dir)

        video_file = obj.get(video_url, tmp_dir)
        print(video_file)
        print(mixed_file)
        dub_file = media.dub(video=video_file,
                             audio=mixed_file,
                             output_dir=tmp_dir)

        ((dub_audio, *_), (dub_video, *_)) = media.probe(dub_file)
        dub_url = f"{env.get_storage_url()}/clips/{dub_file.name}"
        obj.put(dub_file, dub_url)

        dub_clip = Clip(origin=clip.origin,
                        lang=lang,
                        audio=(dub_url, dub_audio),
                        video=(dub_url, dub_video),
                        transcript=zip(events, voices),
                        meta=clip.meta,
                        parent_id=clip_id)

        dub_clip_dict = asdict(dub_clip)
        await doc.put(client, "clips", dub_clip._id, dub_clip_dict)

        return web.json_response(dub_clip_dict)
