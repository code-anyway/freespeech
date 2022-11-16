from dataclasses import replace

from freespeech.lib import language
from freespeech.types import Language, Transcript, TranscriptFormat, TranscriptPlatform

from . import transcript


async def translate(
    source: Transcript | str,
    lang: Language,
    format: TranscriptFormat,
    platform: TranscriptPlatform,
) -> str:
    if isinstance(source, str):
        source = await transcript.load(source)

    translated_events = language.translate_events(source.events, source.lang, lang)
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
        case "GCS":
            raise NotImplementedError("GCS translation is not implemented yet")
