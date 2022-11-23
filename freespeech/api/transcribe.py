import tempfile
from pathlib import Path

from fastapi import APIRouter

from freespeech import env
from freespeech.lib import media, speech, youtube
from freespeech.lib.storage import obj
from freespeech.types import (
    Language,
    ServiceProvider,
    Source,
    SpeechToTextBackend,
    Transcript,
    TranscriptionModel,
    assert_never,
    platform,
)

# Events with the gap greater than GAP_MS won't be concatenated.
GAP_MS = 1400

# Won't attempt concatenating events if one is longer than LENGTH.
PHRASE_LENGTH = 600

# Max download retries for YouTube videos.
MAX_RETRIES = 4

router = APIRouter()


@router.post("/media")
async def ingest(source: str) -> tuple[str | None, str | None]:
    if source.startswith("gs://"):
        return obj.public_url(source), obj.public_url(source)

    with tempfile.TemporaryDirectory() as tempdir:
        audio, video = youtube.download(source, tempdir, max_retries=MAX_RETRIES)
        audio_url = (
            await obj.put(audio, f"{env.get_storage_url()}/media/{Path(audio).name}")
            if audio
            else None
        )
        video_url = (
            await obj.put(video, f"{env.get_storage_url()}/media/{Path(video).name}")
            if video
            else None
        )

        return (audio_url, video_url)


@router.post("/transcribe")
async def transcribe(
    source: str,
    lang: Language,
    backend: SpeechToTextBackend,
) -> Transcript:
    audio_url, video_url = await ingest(source=source)

    if not audio_url:
        raise ValueError(f"No audio stream: {source}")

    match backend:
        case "Machine A" | "Machine B" | "Machine C" | "Machine D":
            provider: ServiceProvider
            model: TranscriptionModel
            match backend:
                case "Machine A":
                    provider = "Google"
                    model = "latest_long"
                case "Machine B":
                    provider = "Deepgram"
                    model = "default"
                case "Machine C":
                    provider = "Azure"
                    model = "default"
                case "Machine D":
                    provider = "Azure"
                    model = "default_granular"
                case never:
                    assert_never(never)
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio = await obj.get(obj.storage_url(audio_url), tmp_dir)
                audio_mono = await media.multi_channel_audio_to_mono(audio, tmp_dir)
                events = await speech.transcribe(
                    file=audio_mono,
                    lang=lang,
                    model=model,
                    provider=provider,
                )
        case "Subtitles":
            events = speech.restore_full_sentences(
                list(youtube.get_captions(source, lang=lang))
            )
        case x:
            assert_never(x)

    # Machine D and Subtitles assume sentence-level timestamps
    # we want to preserve them in the output.
    if backend not in ("Machine D", "Subtitles"):
        events = speech.normalize_speech(
            events, gap_ms=GAP_MS, length=PHRASE_LENGTH, method="break_ends_sentence"
        )

    title = None
    if platform(source) == "YouTube":
        meta = youtube.get_meta(source)
        title = meta.title

    return Transcript(
        title=f"{lang}: {title or 'Untitled'}",
        source=Source(method=backend, url=source),
        events=events,
        lang=lang,
        audio=obj.public_url(audio_url),
        video=obj.public_url(video_url) if video_url else None,
    )
