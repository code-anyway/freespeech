from typing import List

from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import LANGUAGES, Event, Transcript


def _translate_chunks(
    client: translate_api.TranslationServiceClient,
    parent: str,
    chunks: List[str],
    source: str,
    target: str,
) -> List[str]:
    if source == target:
        return chunks

    if source not in LANGUAGES:
        raise ValueError(f"Unsupported source language: {source}")

    if target not in LANGUAGES:
        raise ValueError(f"Unsupported target language: {target}")

    # Detail on supported types can be found here:
    # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": chunks,
            "mime_type": "text/plain",  # or text/html
            "source_language_code": source,
            "target_language_code": target,
        }
    )

    return [t.translated_text for t in response.translations]


def translate(
    text: Transcript | str, source: str | None, target: str
) -> Transcript | str:
    client = translate_api.TranslationServiceClient()
    parent = f"projects/{env.get_project_id()}/locations/global"

    match text:
        case str():
            if source is None:
                raise ValueError("`source` can't be None when type of `text` is `str`")

            (res,) = _translate_chunks(client, parent, [text], source, target)
            return res
        case Transcript((lang)):
            return Transcript(
                lang=target,
                events=[
                    Event(
                        time_ms=e.time_ms,
                        duration_ms=e.duration_ms,
                        chunks=_translate_chunks(
                            client,
                            parent,
                            chunks=e.chunks,
                            source=source or lang,
                            target=target,
                        ),
                    )
                    for e in text.events
                ],
            )
