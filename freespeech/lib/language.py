import re
from dataclasses import replace
from typing import Sequence

from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import Event


def translate_text(text: str, source: str, target: str) -> str:
    if source == target:
        return text

    if not text:
        return text

    client = translate_api.TranslationServiceClient()
    parent = f"projects/{env.get_project_id()}/locations/global"

    # Detail on supported types can be found here:
    # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": [text],
            "mime_type": "text/plain",  # or text/html
            "source_language_code": source,
            "target_language_code": target,
        }
    )

    result = "\n".join([t.translated_text for t in response.translations])

    # Some translations turn "#1#" into "# 1 #", so this should undo that.
    return re.sub(r"#\s*(\d+(\.\d+)?)\s*#", r"#\1#", result)


def translate_events(
    events: Sequence[Event], source: str, target: str
) -> Sequence[Event]:
    return [
        replace(
            event,
            chunks=[translate_text(text, source, target) for text in event.chunks],
        )
        for event in events
    ]
