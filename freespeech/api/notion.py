import logging
from dataclasses import asdict, replace
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from typing import Dict, List, Literal
from uuid import UUID

import aiohttp
from aiohttp import web

from freespeech import client, env
from freespeech.lib import language, media, notion, speech
from freespeech.lib.storage import obj
from freespeech.types import ServiceProvider, assert_never

DUB_CLIENT_TIMEOUT = 3600
CRUD_CLIENT_TIMEOUT = 3600


logger = logging.getLogger(__name__)
routes = web.RouteTableDef()


@routes.post("/notion/{database_id}/process")
async def process(request):
    database_id = request.match_info["database_id"]
    params = await request.json()

    timestamp = params.get("timestamp", None)
    if timestamp:
        timestamp = datetime.fromisoformat(timestamp)

    updated_transcripts = await _process(database_id=database_id, timestamp=timestamp)

    def _serialize(d: Dict) -> Dict:
        return {k: v if not isinstance(v, UUID) else str(v) for k, v in d.items()}

    return web.json_response(
        {k: _serialize(asdict(v)) for k, v in updated_transcripts.items()}
    )


async def _process(
    database_id: str, timestamp: datetime | None
) -> Dict[str, notion.Transcript]:
    transcripts = await notion.get_transcripts(database_id, timestamp=timestamp)
    updated_transcripts: List[notion.Transcript] = []

    for transcript in transcripts:
        updated_transcripts += [await _process_transcript(database_id, transcript)]

    return {transcript._id: transcript for transcript in updated_transcripts}


async def _process_transcript(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    if not transcript.clip_id and transcript.origin:
        transcript = await _upload(database_id, transcript)

    if not transcript.events:
        match transcript.source:
            case "Machine" | "Machine A" | "Machine B":
                transcript = await _transcribe(database_id, transcript)
            case "Subtitles":
                transcript = await _from_subtitles(database_id, transcript)
            case UUID() | "Translate":
                transcript = await _translate(database_id, transcript)
            case never:
                assert_never(never)

    if not transcript.dub_url and transcript.events:
        transcript = await _dub(database_id, transcript)

    return transcript


async def _translate(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    logger.warning(f"Translating: {transcript}")

    transcript_from = await notion.get_transcript(str(transcript.source))
    events = language.translate_events(
        transcript_from.events,
        source=transcript_from.lang,
        target=transcript.lang,
    )

    updated_transcript = await notion.put_transcript(
        database_id=database_id, transcript=replace(transcript, events=events)
    )

    return updated_transcript


async def _from_subtitles(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    logger.warning(f"Syncing Subtitles: {transcript}")

    async with get_crud_client() as _client:
        clip = await client.clip(_client, transcript.clip_id)

    updated_transcript = await notion.put_transcript(
        database_id=database_id,
        transcript=replace(
            transcript,
            events=speech.normalize_speech(clip.transcript),
        ),
    )

    logger.warning(f"Synced Subtitles: {updated_transcript}")

    return updated_transcript


async def _transcribe(
    database_id: str, transcript: notion.Transcript
) -> notion.Transcript:
    logger.warning(f"Transcribing: {transcript}")

    async with get_crud_client() as _client:
        clip = await client.clip(_client, transcript.clip_id)

    audio_url, _ = clip.audio
    with TemporaryDirectory() as tmp_dir:
        audio_file = await obj.get(audio_url, tmp_dir)
        mono_file = await media.multi_channel_audio_to_mono(audio_file, tmp_dir)
        ((audio_info, *_), _) = media.probe(mono_file)
        output_url = f"{env.get_storage_url()}/transcribe/{mono_file.name}"

        await obj.put(mono_file, output_url)

    provider: ServiceProvider

    match transcript.source:
        case "Machine" | "Machine A":
            provider = "Google"
        case "Machine B":
            provider = "Deepgram"
        case "Machine C":
            provider = "Azure"
        case _:
            raise ValueError(f"Unsupported transcription source: {transcript.source}")

    events = await speech.transcribe(
        uri=output_url,
        audio=audio_info,
        lang=transcript.lang,
        model="latest_long",
        provider=provider
    )
    updated_transcript = replace(transcript, events=events)

    logger.warning(f"Trabscribed: {updated_transcript}")

    return await notion.put_transcript(database_id, updated_transcript)


async def _upload(database_id: str, transcript: notion.Transcript) -> notion.Transcript:
    logger.warning(f"Uploading: {transcript}")

    async with get_crud_client() as _client:
        clip = await client.upload(
            http_client=_client,
            video_url=transcript.origin,
            lang=transcript.lang,
        )

    updated_transcript = await notion.put_transcript(
        database_id=database_id,
        transcript=replace(
            transcript,
            clip_id=clip._id,
            meta=replace(clip.meta, description=clip.meta.description),
        ),
        only_props=True,
    )

    logger.warning(f"Uploaded: {updated_transcript}")

    return updated_transcript


async def _dub(database_id: str, transcript: notion.Transcript) -> notion.Transcript:
    logger.warning(f"Dubbing: {transcript}")

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

    logger.warning(f"Dubbed: {updated_transcript}")

    return await notion.put_transcript(database_id, updated_transcript, only_props=True)


def get_dub_client():
    return aiohttp.ClientSession(
        base_url=env.get_dub_service_url(),
        timeout=aiohttp.ClientTimeout(DUB_CLIENT_TIMEOUT),
    )


def get_crud_client():
    return aiohttp.ClientSession(
        base_url=env.get_crud_service_url(),
        timeout=aiohttp.ClientTimeout(CRUD_CLIENT_TIMEOUT),
    )
