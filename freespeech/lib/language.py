import logging
import re
from dataclasses import replace
from typing import Sequence

import deepl
from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import Event

logger = logging.getLogger(__name__)

_deep_l_source_languages = [
    "BG",
    "CS",
    "DA",
    "DE",
    "EL",
    "EN",
    "ES",
    "ET",
    "FI",
    "FR",
    "HU",
    "ID",
    "IT",
    "JA",
    "LT",
    "LV",
    "NL",
    "PL",
    "PT",
    "RO",
    "RU",
    "SK",
    "SL",
    "SV",
    "TR",
    "UK",
    "ZH",
]
_deep_l_target_languages = [
    "BG",
    "CS",
    "DA",
    "DE",
    "EL",
    "EN-GB",
    "EN-US",
    "ES",
    "ET",
    "FI",
    "FR",
    "HU",
    "ID",
    "IT",
    "JA",
    "LT",
    "LV",
    "NL",
    "PL",
    "PT-BR",
    "PT-PT",
    "RO",
    "RU",
    "SK",
    "SL",
    "SV",
    "TR",
    "UK",
    "ZH",
]


def translate_google(text: str, source: str, target: str) -> str:
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


def deep_l_supported(source: str, target: str) -> bool:
    # DeepL uses short language code for all source languages
    source = source.split("-")[0].upper()
    # But it uses a combination of short and long codes for target.
    # Where there is a long code the short one is not supported (e.g. using
    # 'en' where there is 'en-gb' and 'en-us' would yield an error
    target = target.upper()
    target_short = target.split("-")[0].upper()
    return source in _deep_l_source_languages and (
        target in _deep_l_target_languages or target_short in _deep_l_target_languages
    )


def translate_deep_l(text: str, source: str, target: str) -> str:
    """
    Translate text with deepL https://www.deepl.com/en/translator
    Args:
        text: text to translate
        source: text language in format like en-US
        target: desired language in format like en-US

    Returns:
        tranlsated text
    """
    if not text.strip():
        return text

    translator = deepl.Translator(auth_key=env.get_deep_l_key())

    source = source.split("-")[0].upper()
    target = target.upper()
    languages = [str(lang) for lang in translator.get_target_languages()]
    if target not in languages:
        target = target.split("-")[0]

    # Change timecodes to XML to change them back later
    text = re.sub(r"#\s*(\d+(\.\d+)?)+\s*#", r"<t>\1</t>", text)
    result = translator.translate_text(
        tag_handling="xml",
        text=text,
        source_lang=source,
        target_lang=target,
        ignore_tags="t",
        non_splitting_tags="t",
    )
    return re.sub(r"<t>\s*(\d+(\.\d+)?)+\s*</t>", r"#\1#", result.text)


def translate_events(
    events: Sequence[Event], source: str, target: str
) -> Sequence[Event]:
    if deep_l_supported(source, target):
        logger.info(f"Translating chunk with DeepL, language pair {source} to {target}")
        translate_func = translate_deep_l
    else:
        logger.info(
            f"Translating chunk with google (fallback), "
            f"language pair {source} to {target}"
        )
        translate_func = translate_google
    return [
        replace(
            event,
            chunks=[translate_func(text, source, target) for text in event.chunks],
        )
        for event in events
    ]
