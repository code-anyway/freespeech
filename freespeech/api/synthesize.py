import logging
from dataclasses import replace
from tempfile import TemporaryDirectory

from aiohttp import web
from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from freespeech import env
from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Audio, Error, Media, SynthesizeRequest, Video

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)


@routes.post("/synthesize")
async def synthesize(request):
    params = await request.json()

    try:
        request = SynthesizeRequest(**params)
    except ValidationError as e:
        error = Error(message=str(e), state={})
        raise web.HTTPBadRequest(body=pydantic_encoder(error))

    with TemporaryDirectory() as tmp_dir:
        synth_file, _ = await speech.synthesize_events(
            events=request.transcript.events,
            lang=request.transcript.lang,
            output_dir=tmp_dir,
        )
        audio_file = request.transcript.audio and await obj.get(
            request.transcript.audio.url, output_dir=tmp_dir
        )
        video_file = request.transcript.video and await obj.get(
            request.transcript.video.url, output_dir=tmp_dir
        )
        mixed_file = await media.mix(
            files=(audio_file, synth_file),
            weights=(request.transcript.settings.original_audio_level, 10),
            output_dir=tmp_dir,
        )
        dub_file = await media.dub(
            video=video_file, audio=mixed_file, output_dir=tmp_dir
        )
        dub_url = f"{env.get_storage_url()}/output/{dub_file.name}"
        await obj.put(dub_file, dub_url)
        transcript = replace(
            request.transcript,
            video=Media[Video](
                url=dub_url,
                info=None,
            ),
            audio=Media[Audio](
                url=dub_url,
                info=None,
            ),
        )

    return web.json_response(pydantic_encoder(transcript))
