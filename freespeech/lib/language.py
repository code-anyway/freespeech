import logging
import re
from dataclasses import replace
from typing import List, Sequence, Tuple

from aiohttp import ClientSession
from async_lru import alru_cache
from google.cloud import translate as translate_api

from freespeech import env
from freespeech.types import Event

logger = logging.getLogger(__name__)


async def translate_google(text: str, source: str, target: str) -> str:
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


def _deep_l_session() -> ClientSession:
    """
    Get a prepared ClientSession for deepL connection

    Returns:
        aiohttp.ClientSession ready made for deepL api

    """
    key = env.get_deep_l_key()
    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    session = ClientSession("https://api-free.deepl.com/", headers=headers)
    return session


async def translate_deep_l(text: str, source: str, target: str) -> str:
    """
    Translate text with deepL https://www.deepl.com/en/translator
    Args:
        text: text to translate
        source: text language in format like en-US
        target: desired language in format like en-US

    Returns:
        tranlsated text
    """
    source = source.split("-")[0].upper()
    target = target.upper()
    languages = await deep_l_languages()
    if target not in languages[1]:
        target = target.split("-")[0]

    async with _deep_l_session() as session:
        data = {"text": text, "target_lang": target, "source_lang": source}
        async with session.post("/v2/translate", data=data) as resp:
            if not resp.ok:
                text = await resp.text()
                raise ValueError(text)

            result = await resp.json()
            return result["translations"][0]["text"]


@alru_cache
async def deep_l_languages() -> Tuple[List, List]:
    """
    List of deepL languages supported. They have an unusual format like 'RU' or 'EN-US',
    some languages do come with locale and some don't.

    Returns:
        Tuple of two arrays of strings: source_languages, target_languages

    """
    async with _deep_l_session() as session:
        async with session.post("/v2/languages?type=source") as resp:
            source_result = await resp.json()
        async with session.post("/v2/languages?type=target") as resp:
            target_result = await resp.json()
        return (
            [r["language"] for r in source_result],
            [r["language"] for r in target_result],
        )


async def translate_events(
    events: Sequence[Event], source: str, target: str
) -> Sequence[Event]:

    # We would like to try deepL first, and if it fails fallback to Google.
    # deepL, for source languages, has short names like "EN", "RU", and for target it is
    # sometimes "EN-US", "EN-GB" and sometimes short like "UA"
    langs = await deep_l_languages()
    if source.split("-")[0].upper() in langs[0] and (
        target.upper() in langs[1] or target.split("-")[0].upper() in langs[1]
    ):
        translate_func = translate_deep_l
    else:
        translate_func = translate_google

    # there is something wrong with the async hierarchy of comprehensions here so had to
    # rewrite it to an explicit arrays alex che 20220907
    result = []
    for event in events:
        translated_event = replace(
            event,
            chunks=[
                await translate_func(text, source, target) for text in event.chunks
            ],
        )
        result.append(translated_event)
    return result
