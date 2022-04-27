from dataclasses import replace
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from typing import Dict
from uuid import UUID

import aiohttp
from aiohttp import web

from freespeech import client, env
from freespeech.lib import language, media, notion, speech
from freespeech.lib.storage import obj
from freespeech.types import assert_never

routes = web.RouteTableDef()


async def process(database_id: str) -> Dict[str, notion.Transcript]:
    transcripts = await notion.get_transcripts(database_id, timestamp=None)
    updated_transcripts: Dict[str, notion.Transcript] = {}

    for transcript in transcripts:
        if not transcript.clip_id and transcript.origin:
            transcript = await _upload(transcript)

        if not transcript.events:
            match transcript.source:
                case "Machine":
                    transcript = await _transcribe(database_id, transcript)
                    updated_transcripts[transcript._id] = transcript
                case "Subtitles":
                    transcript = await _from_subtitles(database_id, transcript)
                    updated_transcripts[transcript._id] = transcript
                case UUID() | "Translate":
                    transcript = await _translate(database_id, transcript)
                    updated_transcripts[transcript._id] = transcript
                case never:
                    assert_never(never)

        if not transcript.dub_url:
            transcript = await _dub(database_id, transcript)
            updated_transcripts[transcript._id] = transcript

    return updated_transcripts


async def _translate(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    transcript_from = await notion.get_transcript(str(transcript.source))
    events = language.translate_events(
        transcript_from.events,
        source=transcript_from.lang,
        target=transcript.lang,
    )

    transcript_translated = replace(transcript, events=events)
    transcript_translated = await notion.put_transcript(
        database_id=database_id, transcript=transcript_translated
    )

    return transcript_translated


async def _from_subtitles(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    async with get_crud_client() as _client:
        clip = await client.clip(_client, transcript.clip_id)

    new_transcript = await notion.put_transcript(
        database_id=database_id,
        transcript=replace(
            transcript,
            events=speech.normalize_speech(clip.transcript),
        ),
    )

    return new_transcript


async def _transcribe(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    async with get_crud_client() as _client:
        clip = await client.clip(_client, transcript.clip_id)

    audio_url, _ = clip.audio
    with TemporaryDirectory() as tmp_dir:
        audio_file = await obj.get(audio_url, tmp_dir)
        mono_file = await media.multi_channel_audio_to_mono(audio_file, tmp_dir)
        ((audio_info, *_), _) = media.probe(mono_file)
        output_url = f"{env.get_storage_url()}/transcribe/{mono_file.name}"

        await obj.put(mono_file, output_url)

    events = await speech.transcribe(
        uri=output_url,
        audio=audio_info,
        lang=transcript.lang,
        model="latest_long",
    )
    transcribed = replace(transcript, clip_id=transcript.clip_id, events=events)

    return await notion.put_transcript(database_id, transcribed)


async def _upload(transcript: notion.Transcript) -> notion.Transcript:
    async with get_crud_client() as _client:
        clip = await client.upload(
            http_client=_client,
            video_url=transcript.origin,
            lang=transcript.lang,
        )

    return replace(
        transcript,
        clip_id=clip._id,
        meta=replace(clip.meta, description=clip.meta.description),
    )


async def _dub(database_id: str, transcript: notion.Transcript) -> notion.Transcript:
    async with get_crud_client() as _client:
        clip = await client.clip(_client, transcript.clip_id)

    async with get_dub_client() as _client:
        dubbed_clip = await client.dub(
            http_client=_client,
            clip_id=clip._id,
            transcript=transcript.events,
            default_character=transcript.voice.character,
            lang=transcript.lang,
            pitch=transcript.voice.pitch,
            weights=transcript.weights,
        )

    async with get_crud_client() as _client:
        public_url = await client.video(_client, dubbed_clip._id)

    updated_transcript = replace(
        transcript,
        dub_url=public_url,
        dub_timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
    return await notion.put_transcript(database_id, updated_transcript)


def get_dub_client():
    return aiohttp.ClientSession(base_url=env.get_dub_service_url())


def get_crud_client():
    return aiohttp.ClientSession(base_url=env.get_crud_service_url())
