from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

from aiohttp import web

from freespeech import client, env
from freespeech.lib import language, notion, speech, youtube

routes = web.RouteTableDef()


async def init(transcript: notion.Transcript) -> notion.Transcript:
    if transcript.clip_id is None:
        clip = await client.upload(
            service_url=env.get_crud_service_url(),
            video_url=transcript.origin,
            lang=transcript.lang,
        )
        updated_transcript = replace(transcript, clip_id=clip._id)
        return updated_transcript
    else:
        clip = await client.clip(
            service_url=env.get_crud_service_url(), clip_id=transcript.clip_id
        )
        return transcript, clip


async def dub(page_id: str) -> notion.Transcript:
    transcript = notion.get_transcript(page_id)
    transcript = await init(transcript)
    new_clip = await client.dub(
        env.get_dub_service_url(),
        transcript.clip_id,
        transcript=transcript.events,
        default_character=transcript.voice.character,
        lang=transcript.lang,
        pitch=transcript.voice.pitch,
        weights=transcript.weights,
    )
    dub_url = await client.video(
        service_url=env.get_crud_service_url(), clip_id=new_clip._id
    )

    updated_transcript = replace(
        transcript,
        clip_id=new_clip._id,
        dub_url=dub_url,
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )

    return notion.put_transcript(env.get_notion_database_id(), updated_transcript)


async def refresh(page_id: str) -> notion.Transcript:
    transcript = notion.get_transcript(page_id)

    match transcript.source:
        case "Machine":
            clip = await client.clip(env.get_crud_service_url(), transcript.clip_id)
            audio_url, audio = clip.audio
            events = await speech.transcribe(audio_url, audio, transcript.lang)
        case "Subtitles":
            events = youtube.get_captions(transcript.origin, transcript.lang)
        case UUID():
            source_transcript = notion.get_transcript(str(transcript.source))
            events = language.translate_events(
                events=source_transcript.events,
                source=source_transcript.lang,
                target=transcript.lang,
            )
        case never:
            assert_never(never)

    updated_transcript = replace(transcript, events=events)
    notion.put_transcript(env.get_notion_database_id(), updated_transcript)

    return transcript
