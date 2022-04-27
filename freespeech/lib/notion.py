import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Literal, Sequence, Tuple, TypeGuard
from uuid import UUID
from zoneinfo import ZoneInfo

import aiohttp

from freespeech import env, types
from freespeech.lib import text
from freespeech.types import Event, Language, Meta, Voice, assert_never, url

logger = logging.getLogger(__name__)

NOTION_RICH_TEXT_CONTENT_LIMIT = 200

PROPERTY_NAME_PAGE_TITLE = "Name"
PROPERTY_NAME_ORIGIN = "Origin"
PROPERTY_NAME_LANG = "Speak In"
PROPERTY_NAME_SOURCE = "Transcript Source"
PROPERTY_NAME_CHARACTER = "Voice"
PROPERTY_NAME_PITCH = "Pitch"
PROPERTY_NAME_WEIGHTS = "Weights"
PROPERTY_NAME_TITLE = "Title"
PROPERTY_NAME_DESCRIPTION = "Description"
PROPERTY_NAME_TAGS = "Tags"
PROPERTY_NAME_DUB_TIMESTAMP = "Dub timestamp"
PROPERTY_NAME_DUB_URL = "Dub URL"
PROPERTY_NAME_CLIP_ID = "Clip ID"
PROPERTY_NAME_TRANSLATED_FROM = "Translated From"

Source = Literal["Machine", "Subtitles", "Tranlate"]
HTTPVerb = Literal["GET", "PATCH", "DELETE", "POST"]


def is_source(val: str) -> TypeGuard[Source]:
    return val in ("Machine", "Subtitles", "Translate")


@dataclass(frozen=True)
class Transcript:
    title: str
    origin: url
    lang: Language
    source: Source | UUID
    events: Sequence[Event]
    meta: Meta | None
    dub_timestamp: str | None
    dub_url: url | None
    clip_id: str
    _id: str | None
    voice: Voice = Voice(character="Grace Hopper")
    weights: Tuple[int, int] = (2, 10)


QueryOperator = Literal["greater_than", "equals", "after", "any"]


NOTION_API_MAX_PAGE_SIZE = 100
NOTION_API_HEADERS = {
    "Accept": "application/json",
    "Notion-Version": "2022-02-22",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {env.get_notion_token()}",
}
NOTION_API_BASE_URL = "https://api.notion.com"


async def query(
    database_id: str,
    property_name: str,
    property_type: str,
    operator: QueryOperator,
    value: str | Dict,
) -> List[str]:
    """Get all pages where property matches the expression."""
    page_ids = []

    # How filtering in Notion API works:
    # https://developers.notion.com/reference/post-database-query-filter#rollup-filter-condition  # noqa E501
    payload: Dict[str, Dict | int] = {
        "filter": {"property": property_name, property_type: {operator: value}},
    }
    payload["page_size"] = NOTION_API_MAX_PAGE_SIZE

    # TODO (astaff): There must be a more pythonic and reusable way
    # to handle pagination it REST APIs but I can't quite express it yet.
    while True:
        data = await _make_api_call(
            verb="POST", url=f"/v1/databases/{database_id}/query", payload=payload
        )

        page_ids += [page["id"] for page in data["results"] if not page["archived"]]

        if data["has_more"]:
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return page_ids


async def get_properties(page_id: str) -> Dict:
    """Get Notion API representation of page properties.

    Args:
        page_id: id of a page.

    Returns:
        Dict with property values in Notion API format.
        Details: https://developers.notion.com/reference/property-value-object
        Note: It doesn't return page content. Use `get_child_blocks`
        for that.
    """
    result = await _make_api_call(verb="GET", url=f"/v1/pages/{page_id}")
    return result["properties"]


async def get_transcript(page_id: str) -> Transcript:
    """Parse Notion page and generate transcript.

    Args:
        page_id: Notion page ID.

    Returns:
        Transcript generated from page properties and content.
    """
    properties = await get_properties(page_id)
    results = await get_child_blocks(page_id)
    blocks = [r for r in results if not r["archived"]]

    transcript = parse_transcript(page_id, properties=properties, blocks=blocks)

    return transcript


def parse_properties(page: Dict) -> Dict[str, Any]:
    return {property: _parse_value(value) for property, value in page.items()}


def _parse_value(
    value: Dict, value_type: str | None = None
) -> str | List[str] | List[Dict] | None:
    # Sometimes Notion response doesn't have "type" key
    # and the caller will need to give a hint.
    _type = value_type or value["type"]
    match _type:
        case "multi_select":
            return [v["name"] for v in value[_type]]
        case "select":
            if value[_type] is None:
                return None
            return value[_type]["name"]
        case "title" | "rich_text":
            return "".join(
                v.get("plain_text", None) or v["text"]["content"] for v in value[_type]
            )
        case "heading_1" | "heading_2" | "heading_3" | "paragraph":
            return _parse_value(value[_type], value_type="rich_text")
        case "date":
            start = datetime.fromisoformat(value[_type]["start"])
            time_zone = value[_type]["time_zone"]
            if time_zone:
                start = start.astimezone(tz=ZoneInfo(time_zone))
            return start.isoformat()
        case _:
            return value[_type]


async def get_child_blocks(page_id: str) -> List[Dict]:
    result = await _make_api_call(verb="GET", url=f"/v1/blocks/{page_id}/children")
    return result["results"]


async def append_child_blocks(page_id: str, blocks: List[Dict]) -> List[Dict]:
    result = await _make_api_call(
        verb="PATCH", url=f"/v1/blocks/{page_id}/children", payload={"children": blocks}
    )
    return result["results"]


async def delete_block(block_id: str) -> None:
    result = await _make_api_call(verb="DELETE", url=f"/v1/blocks/{block_id}")
    if result:
        logger.warning(f"Non-empty response while deleting block {block_id}: {result}")


def get_updated_pages(db_id: str, timestamp: str) -> List[str]:
    """Get all pages that were updated after `timestamp`."""
    raise NotImplementedError()


def render_transcript(transcript: Transcript) -> Tuple[Dict[str, Any], List[Dict]]:
    if isinstance(transcript.source, UUID):
        source = "Translate"
        translated_from = str(transcript.source)
    else:
        source = transcript.source
        translated_from = None

    if transcript.voice is not None:
        character = transcript.voice.character
        pitch = transcript.voice.pitch
    else:
        character = None
        pitch = None

    if transcript.weights is not None:
        weights = ", ".join(str(w) for w in transcript.weights)
    else:
        weights = None

    if transcript.meta is not None:
        title = transcript.meta.title
        description = transcript.meta.description
        tags = transcript.meta.tags

    properties = {
        PROPERTY_NAME_PAGE_TITLE: {
            "title": [{"type": "text", "text": {"content": transcript.title}}],
        },
        PROPERTY_NAME_ORIGIN: {"url": transcript.origin},
        PROPERTY_NAME_LANG: {"select": {"name": transcript.lang}},
        PROPERTY_NAME_SOURCE: {"select": {"name": source}},
        PROPERTY_NAME_CHARACTER: {"select": {"name": character} if character else {}},
        PROPERTY_NAME_PITCH: {"number": pitch},
        PROPERTY_NAME_WEIGHTS: render_text(weights),
        PROPERTY_NAME_TITLE: render_text(title),
        PROPERTY_NAME_DESCRIPTION: render_text(description),
        PROPERTY_NAME_TAGS: {"multi_select": [{"name": tag} for tag in tags or []]},
        PROPERTY_NAME_DUB_TIMESTAMP: render_text(transcript.dub_timestamp or ""),
        PROPERTY_NAME_DUB_URL: {"url": transcript.dub_url},
        PROPERTY_NAME_CLIP_ID: render_text(transcript.clip_id),
        PROPERTY_NAME_TRANSLATED_FROM: {
            "relation": [{"id": translated_from}] if translated_from else []
        },
    }

    # Flatten event blocks
    blocks: List[Dict] = sum([render_event(event) for event in transcript.events], [])

    return properties, blocks


def render_text(t: str) -> Dict:
    return {
        "rich_text": [
            {"text": {"content": chunk}}
            for chunk in text.chunk_raw(t, NOTION_RICH_TEXT_CONTENT_LIMIT)
        ]
    }


def parse_events(blocks: List[Dict]) -> Sequence[Event]:
    events: Dict[Tuple[int, int], List[str]] = dict()

    HEADINGS = ["heading_1", "heading_2", "heading_3"]

    for block in blocks:
        _type = block["type"]
        if _type in HEADINGS:
            value = _parse_value(block)
            assert isinstance(value, str)
            key = parse_time_interval(value)
            events[key] = events.get(key, [])
        elif _type == "paragraph":
            value = _parse_value(block)
            if not key:
                logger.warning(f"Paragraph without timestamp: {value}")
            assert isinstance(value, str)
            events[key].append(value)

    return [
        Event(time_ms=time_ms, duration_ms=duration_ms, chunks=chunks)
        for (time_ms, duration_ms), chunks in events.items()
    ]


def parse_transcript(
    _id: str, properties: Dict[str, Any], blocks: List[Dict]
) -> Transcript:
    properties = parse_properties(properties)
    source = properties[PROPERTY_NAME_SOURCE]
    translated_from = properties[PROPERTY_NAME_TRANSLATED_FROM]

    if not is_source(source):
        raise ValueError(f"Invalid transcript source: {source}")

    if source == "Translate":
        source = UUID(translated_from[0]['id']) if translated_from is not None else None

    lang = properties[PROPERTY_NAME_LANG]
    if not types.is_language(lang):
        raise ValueError(f"Invalid language: {lang}")

    character = properties[PROPERTY_NAME_CHARACTER]
    if not types.is_character(character):
        raise ValueError(f"Invalid character name: {character}")

    pitch = properties[PROPERTY_NAME_PITCH]
    if pitch:
        pitch = float(pitch)

    voice = Voice(character=character, pitch=pitch)

    weights = properties[PROPERTY_NAME_WEIGHTS]
    if weights:
        weights = tuple(int(w.strip()) for w in weights.split(","))

    meta = Meta(
        title=properties[PROPERTY_NAME_TITLE],
        description=properties[PROPERTY_NAME_DESCRIPTION],
        tags=properties[PROPERTY_NAME_TAGS],
    )

    return Transcript(
        title=str(properties[PROPERTY_NAME_PAGE_TITLE]),
        origin=str(properties[PROPERTY_NAME_ORIGIN]),
        lang=lang,
        source=source,
        events=parse_events(blocks),
        voice=voice,
        weights=weights,
        meta=meta,
        dub_timestamp=properties[PROPERTY_NAME_DUB_TIMESTAMP],
        dub_url=properties[PROPERTY_NAME_DUB_URL],
        clip_id=properties[PROPERTY_NAME_CLIP_ID],
        _id=_id,
    )


async def replace_blocks(page_id: str, blocks: List[Dict]) -> List[Dict]:
    child_blocks = await get_child_blocks(page_id)
    for block in child_blocks:
        await delete_block(block["id"])
    return await append_child_blocks(page_id, blocks)


async def create_page(database_id: str, properties: Dict, blocks: List[Dict]) -> Dict:
    payload = {
        "parent": {"type": "database_id", "database_id": database_id},
        "properties": properties,
    }

    if blocks:
        payload["children"] = blocks

    result = await _make_api_call(verb="POST", url="/v1/pages", payload=payload)

    return result


async def update_page_properties(page_id: str, properties: Dict) -> Dict:
    result = await _make_api_call(
        verb="PATCH", url=f"/v1/pages/{page_id}", payload={"properties": properties}
    )
    return result


async def put_transcript(
    database_id: str,
    transcript: Transcript,
) -> Transcript:
    properties, blocks = render_transcript(transcript)

    if transcript._id is None:
        result = await create_page(
            database_id=database_id, properties=properties, blocks=blocks
        )
    else:
        result = await update_page_properties(
            page_id=transcript._id, properties=properties
        )

        if blocks:
            blocks = await replace_blocks(transcript._id, blocks)

    return parse_transcript(
        result["id"], properties=result["properties"], blocks=blocks
    )


def parse_time_interval(interval: str) -> Tuple[int, int]:
    """Parses HH:MM:SS.fff/HH:MM:SS.fff into (start_ms, duration_ms).

    Args:
        interval: start and finish encoded as
            two ISO 8601 formatted timestamps separated by "/"

    Returns:
        Event start time and duration in milliseconds.
    """

    # TODO (astaff): couldn't find a sane way to do that
    # other than parsing it as datetime from a custom
    # ISO format that ingores date. Hence this.
    def _to_milliseconds(t: time):
        return (
            t.hour * 60 * 60 * 1_000
            + t.minute * 60 * 1_000
            + t.second * 1_000
            + t.microsecond // 1_000
        )

    start, duration = [s.strip() for s in interval.split("/")]

    start_ms = _to_milliseconds(time.fromisoformat(start))
    finish_ms = _to_milliseconds(time.fromisoformat(duration))

    return start_ms, finish_ms - start_ms


def unparse_time_interval(time_ms: int, duration_ms: int) -> str:
    """Generates HH:MM:SS.fff/HH:MM:SS.fff representation for a time interval.

    Args:
        time_ms: interval start time in milliseconds.
        duration_ms: interval duration in milliseconds.

    Returns:
       Interval start and finish encoded as
       two ISO 8601 formatted timespamps separated by "/".
    """
    start_ms = time_ms
    finish_ms = time_ms + duration_ms

    def _ms_to_iso_time(ms: int) -> str:
        t = datetime.fromtimestamp(ms / 1000.0).time()
        return t.isoformat()

    return f"{_ms_to_iso_time(start_ms)}/{_ms_to_iso_time(finish_ms)}"


def render_event(event: Event) -> List[Dict]:
    """Generates list of Notion blocks representing a speech event."""
    HEADER = "heading_3"
    text = {
        "type": "text",
        "text": {"content": unparse_time_interval(event.time_ms, event.duration_ms)},
    }
    header = {
        "object": "block",
        "type": HEADER,
        HEADER: {"rich_text": [text]},
    }
    paragraphs = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": render_text(chunk),
        }
        for chunk in event.chunks
    ]

    return [header, *paragraphs]


async def _parse_api_response(response: aiohttp.ClientResponse) -> Dict:
    result = await response.json()

    if response.status == 200:
        return result
    else:
        raise RuntimeError(
            f"Error making API call to {response.url}: {result['message']}"
        )


async def _make_api_call(verb: HTTPVerb, url: url, payload: Dict | None = None) -> Dict:
    async with aiohttp.ClientSession(
        base_url=NOTION_API_BASE_URL, headers=NOTION_API_HEADERS
    ) as session:
        match verb:
            case "GET":
                async with session.get(url) as response:
                    return await _parse_api_response(response)
            case "POST":
                async with session.post(url, json=payload) as response:
                    return await _parse_api_response(response)
            case "DELETE":
                async with session.delete(url) as response:
                    return await _parse_api_response(response)
            case "PATCH":
                async with session.patch(url, json=payload) as response:
                    return await _parse_api_response(response)
            case never:
                assert_never(never)
