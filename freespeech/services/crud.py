from tempfile import TemporaryDirectory
from aiohttp import web
from freespeech.api import media, youtube
from freespeech.api.storage import doc, obj
from freespeech.types import Clip
from freespeech import env
from dataclasses import asdict
import logging


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

        video_url = f"{env.get_storage_url()}/clips/{audio_file.name}"
        obj.put(src=video_file, dst=video_url)

        ((audio, *_), _) = media.probe(audio_file)
        (_, (video, *_)) = media.probe(video_file)

        clip = Clip(origin=url,
                    lang=lang,
                    audio=(audio_url, audio),
                    video=(audio_url, video),
                    transcript=[],
                    meta=meta,
                    parent_id=None)

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


@routes.get("/clips/latest/{encoded_url}/{lang}")
async def latest(request):
    pass


# Service: CRUD
# LIST /media/
# Get all media records

# Service: CRUD
# LIST /media/{id}
# Get all media records for an ID.

# Service: CRUD
# GET /media/{id}/{lang}
# Get a media record for a given id and language.

# Service: CRUD
# GET /media/{id}/{lang}/transcript
# Get transcript in lang for media

# Service: CRUD
# POST /media/{id}/{lang}/transcript {events}
# Updates transcript for a language.
