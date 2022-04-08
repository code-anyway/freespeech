from freespeech import datastore
from freespeech.notion import client as nc
from freespeech.types import Transcript


from typing import Dict


from aiohttp import web


routes = web.RouteTableDef()


@routes.get("/dubs/from_notion/{page_id}")
async def dubs_from_notion(request):
    page_id = request.match_info.get("page_id", None)
    dub = create_voiceover_from_notion_page(page_id)
    return web.json_response(dub)


def create_voiceover_from_notion_page(page_id: str) -> Dict[str, object]:
    page_info = nc.get_page_info(page_id)
    properties = nc.get_page_properties(page=page_info)

    def _unpack_rollup_property(property: Dict) -> str:
        value = nc.parse_property_value(property)
        assert type(value) is list
        assert type(value[0]) is dict

        res = nc.parse_property_value(value[0])
        assert type(res) is str

        return res

    origin = _unpack_rollup_property(properties["Origin"])
    source_lang = _unpack_rollup_property(properties["Source Language"])
    voice = properties["Voice"]
    ratio = 0.8 if not (value := properties["Weight"]) else float(value)

    transcript = import_transcript_from_notion_page(page_id)

    media = voiceover(
        url=origin,
        transcript_id=transcript._id,
        source_lang=source_lang,
        voice=voice,
        ratio=ratio,
    )

    assert media.video, "Translated media has no video"
    video = media.video[0]

    assert video.url, "Resulting video has no URL"
    url = video.url

    result = {
        "url": url.replace("gs://", "https://storage.googleapis.com/"),
        "duration_ms": video.duration_ms,
        "title": media.title,
        "description": media.description,
        "tags": media.tags,
    }

    return result


def import_transcript_from_notion_page(page_id: str) -> Transcript:
    transcript = nc.get_transcript(page_id)
    datastore.put(transcript)
    return transcript


def synthesize(transcript_id: str, voice: str) -> Audio:
    if voice not in VOICES:
        raise ValueError(
            f"Invalid voice {voice}. Expected values: {VOICES.keys()}")
    transcript = datastore.get(transcript_id, "transcript")

    if transcript.lang not in VOICES[voice]:
        raise ValueError(f"{transcript.lang} is not supported for {voice}")

    audio = speech.synthesize(
        transcript,
        VOICES[voice][transcript.lang],
        storage_url=env.get_storage_url()
    )

    datastore.put(audio)

    return audio


def voiceover(
    url: str, transcript_id: str, source_lang: str, voice: str, ratio: float
) -> Media:
    media = get_media(url)
    new_audio = synthesize(transcript_id, voice)

    original_audio, *_ = media.audio
    if _:
        logger.warning(f"Additional audio for {url}: {_}")

    MAX_WEIGHT = 10
    weights = [round(MAX_WEIGHT * (1 - ratio)), MAX_WEIGHT]

    logger.info(f"ffmpeg amix weights={weights} (ratio={ratio})")
    mixed_audio = media_ops.mix(
        [original_audio, new_audio],
        weights=weights,
        storage_url=env.get_storage_url()
    )

    video, *_ = media.video
    if _:
        logger.warning(f"Additional video for {url}: {_}")

    final_video, final_audio = media_ops.add_audio(
        video, mixed_audio, storage_url=env.get_storage_url()
    )

    def _translate(text: str) -> str:
        assert new_audio.lang

        return str(language.translate(text, source_lang, new_audio.lang))

    new_media = Media(
        audio=[final_audio],
        video=[final_video],
        title=_translate(media.title),
        description=_translate(media.description),
        tags=media.tags,
        origin=f"voiceover:{transcript_id}:{media.origin}",
    )

    datastore.put(new_media)

    return new_media
