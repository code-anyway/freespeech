from dataclasses import replace
from typing import List

from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import Event


def _translate_chunks(
    chunks: List[str],
    source: str,
    target: str,
) -> List[str]:
    if source == target:
        return chunks

    client = translate_api.TranslationServiceClient()
    parent = f"projects/{env.get_project_id()}/locations/global"

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


def translate_text(text: str, source: str, target: str) -> str:
    chunks = _translate_chunks([text], source, target)
    return "\n".join(chunks)


def translate_events(events: List[Event], source: str, target: str) -> List[Event]:
    return [
        replace(event, chunks=_translate_chunks(event.chunks, source, target))
        for event in events
    ]
