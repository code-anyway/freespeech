import logging
from dataclasses import asdict
from tempfile import TemporaryDirectory

from aiohttp import web

from freespeech import env
from freespeech.api import media, youtube
from freespeech.api.storage import doc, obj
from freespeech.types import Clip

logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.post("/clips/upload")
async def upload(request):
    params = await request.json()

    url = params["url"]
    lang = params["lang"]

    # TODO (astaff): collect metrics with endpoints runtime
    logger.info("Downloading {url} {lang}")

    with TemporaryDirectory() as tmp_dir:
        audio_file, video_file, meta = youtube.download(url, tmp_dir)

        audio_url = f"{env.get_storage_url()}/clips/{audio_file.name}"
        obj.put(src=audio_file, dst=audio_url)

        video_url = f"{env.get_storage_url()}/clips/{video_file.name}"
        obj.put(src=video_file, dst=video_url)

        ((audio, *_), _) = media.probe(audio_file)
        (_, (video, *_)) = media.probe(video_file)

        clip = Clip(
            origin=url,
            lang=lang,
            audio=(audio_url, audio),
            video=(video_url, video),
            transcript=[],
            meta=meta,
            parent_id=None,
        )

        client = doc.google_firestore_client()
        clip_dict = asdict(clip)
        await doc.put(client, coll="clips", key=clip._id, value=clip_dict)

    # TODO (astaff): collect metrics with endpoints runtime
    logger.info("Finished downloading {url} {lang}: clip _id='{clip._id}'")

    return web.json_response(clip_dict)


@routes.get("/clips/{clip_id}")
async def get(request):
    clip_id = request.match_info["clip_id"]

    client = doc.google_firestore_client()
    clip_dict = await doc.get(client, coll="clips", key=clip_id)

    return web.json_response(clip_dict)


@routes.get("/clips/{clip_id}/video")
async def get_video(request):
    clip_id = request.match_info["clip_id"]

    client = doc.google_firestore_client()
    clip_dict = await doc.get(client, coll="clips", key=clip_id)

    if not clip_dict["video"]:
        return web.HTTPNotFound(f"No video for {clip_id}.")
    url, _ = clip_dict["video"]
    url = obj.get_public_url(url)

    return web.json_response({"url": url})


@routes.get("/clips/latest/{url}/{lang}")
async def latest_by_lang(request):
    url = request.match_info["url"]
    lang = request.match_info["lang"]

    client = doc.google_firestore_client()
    clips = await doc.query(
        client,
        coll="clips",
        attr="origin",
        op="==",
        value=url,
        order=("last_updated", "DESCENDING"),
    )

    if not clips:
        return web.HTTPNotFound(f"No clips for {url}.  " "Consider uploading it first.")

    clip, *_ = [clip for clip in clips if clip["lang"] == lang]

    return web.json_response(clip)


@routes.get("/clips/latest/{url}")
async def latest_all_langs(request):
    url = request.match_info["url"]
    client = doc.google_firestore_client()
    clips = await doc.query(
        client,
        coll="clips",
        attr="origin",
        op="==",
        value=url,
        order=("last_updated", "ASCENDING"),
    )

    if not clips:
        return web.HTTPNotFound(f"No clips for {url}.  " "Consider uploading it first.")

    response = dict((clip["lang"], clip) for clip in clips)

    return web.json_response(response)


@routes.post("/clips/{_id}")
async def update(request):
    _id = request.match_info["_id"]
    clip = await request.json()

    filter_keys = ("_id", "last_updated", "parent_id")
    clip = {k: v for k, v in clip.items() if k not in filter_keys}
    new_clip = Clip(**clip, parent_id=_id)

    client = doc.google_firestore_client()
    value = asdict(new_clip)
    await doc.put(client, "clips", key=new_clip._id, value=value)

    return web.json_response(value)
