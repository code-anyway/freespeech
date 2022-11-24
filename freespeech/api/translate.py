from dataclasses import replace

from fastapi import APIRouter

from freespeech.lib import language
from freespeech.types import (
    Language,
    Transcript,
    TranscriptFormat,
    TranscriptPlatform,
    assert_never,
)

from . import transcript

router = APIRouter()


@router.post("/translate")
async def translate(
    source: Transcript | str,
    lang: Language,
    format: TranscriptFormat,
    platform: TranscriptPlatform,
) -> str:
    if isinstance(source, str):
        source = await transcript.load(source)

    translated_events = [
        replace(translated_event, comment=" ".join(event.chunks))
        for event, translated_event in zip(
            source.events, language.translate_events(source.events, source.lang, lang)
        )
    ]
    translated = replace(
        source,
        events=translated_events,
        lang=lang,
    )

    match platform:
        case "Google":
            return await transcript.save(
                translated, platform=platform, format=format, location=None
            )
        case "Notion":
            raise NotImplementedError("Notion translation is not implemented yet")
        case x:
            assert_never(x)
