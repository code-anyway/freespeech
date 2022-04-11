import logging
from datetime import datetime, time
from typing import Dict, List, Tuple, Literal

import requests

from freespeech import env
from freespeech.types import Event, Language

logger = logging.getLogger(__name__)


QueryOperator = Literal["greater_than", "equals", "after"]


NOTION_MAX_PAGE_SIZE = 100

HEADERS = {
    "Accept": "application/json",
    "Notion-Version": "2022-02-22",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {env.get_notion_token()}",
}


def get_pages(database_id: str, page_size: int = 100) -> List[str]:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    page_ids = []
    payload = {"page_size": page_size}
    while True:
        response = requests.request("POST", url, json=payload, headers=HEADERS)
        data = response.json()

        page_ids += [
            page["id"] for page in data["results"]
            if not page["archived"]]

        if data["has_more"]:
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return page_ids


def query(
    db_id: str,
    property_name: str,
    property_type: str,
    operator: QueryOperator,
    value: str
) -> List[str]:
    """Get all pages where property matches the expression."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    page_ids = []
    payload = {
        "filter": {
            "property": property_name,
            property_type: {
                operator: value
            }
        },
        "page_size": NOTION_MAX_PAGE_SIZE
    }

    while True:
        response = requests.request("POST", url, json=payload, headers=HEADERS)
        data = response.json()

        page_ids += [
            page["id"] for page in data["results"]
            if not page["archived"]]

        if data["has_more"]:
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return page_ids


def get_page_properties(_id: str) -> Dict:
    """Get page information.

    Args:
        _id: id of a page.

    Returns:
        Dict with page info.
        Note: it doesn't return page content. Use `get_child_blocks`
        for that.
    """
    url = f"https://api.notion.com/v1/pages/{_id}"
    response = requests.get(url, headers=HEADERS)
    page = response.json()

    properties = {
        property: _parse_value(value)
        for property, value in page["properties"].items()
    }

    return properties


def _parse_value(value: Dict) -> str | List[str] | List[Dict]:
    _type = value["type"]

    match _type:
        case "multi_select":
            return [v["name"] for v in value[_type]]
        case "select":
            return value[_type]["name"]
        case "title" | "rich_text" | "paragraph" | \
             "heading_1" | "heading_2" | "heading_3":
            return "\n".join(v["plain_text"] for v in value[_type])
        case _:
            return value[_type]


def get_page_blocks(_id: str) -> Dict:
    """Get child blocks for a page.

    Args:
        _id: id of a page.

    Returns:
        Dict with child block content.
    """
    url = f"https://api.notion.com/v1/blocks/{_id}/children"
    response = requests.get(url, headers=HEADERS)
    return response.json()


def get_transcript(page_id: str) -> List[Event]:
    """Parse Notion's page and generate transcript.

    Args:
        page_id: Notion page ID.

    Returns:
        Transcript represented as list of speech events.
    """
    HEADINGS = [
        "heading_1",
        "heading_2",
        "heading_3",
    ]

    blocks = get_page_blocks(page_id)
    results = (r for r in blocks["results"] if not r["archived"])
    events: Dict[Tuple[int, int], List[str]] = dict()

    for result in results:
        _type = result["type"]
        if _type in HEADINGS:
            print(result)
            value = _parse_value(result[_type])
            assert isinstance(value, str)
            key = _parse_event(value)
            events[key] = events.get(key, [])
        elif _type == "paragraph":
            value = _parse_value(result[_type])
            if not key:
                logger.warning(f"Paragraph without timestamp: {value}")
            assert isinstance(value, str)
            events[key].append(value)

    return [
        Event(time_ms=time_ms, duration_ms=duration_ms, chunks=chunks)
        for (time_ms, duration_ms), chunks in events.items()
    ]


def get_updated_pages(db_id: str, timestamp: str) -> List[str]:
    """Get all pages that were updated after `timestamp`."""
    raise NotImplementedError()


def get_transcripts(db_id: str, url: str) -> Dict[Language, List[Event]]:
    """Get all transcripts for a video url.

    Args:
        db_id: id of a Notion database containing transcripts.
        url: url of a video transcripts are associated with.

    Returns:
        A dict with transcript's language as a key
        and speech events as a value.
    """

    page_ids = query(
        db_id=db_id,
        property_name="Origin",
        property_type="rich_text",
        operator="equals",
        value=url
    )

    transcripts = {
        get_page_properties(_id)["Language"]: get_transcript(_id)
        for _id in page_ids
    }

    return transcripts


def add_transcript(
    project_db_id: str,
    transcript_db_id: str,
    url: str,
    lang: str,
    title: str,
    events: List[Event]
) -> str:
    url = "https://api.notion.com/v1/pages"

    project_id, *tail = query(project_db_id, "Video", "url", "equals", url)
    logger.warning(
        f"Multiple projects with the same Video url in "
        f"{project_db_id}: {[project_id] + tail}")

    # Flatten event blocks
    blocks: List[Dict] = sum(
        [_get_blocks_from_event(event) for event in events], [])

    payload = {
        "parent": {
            "type": "database_id",
            "database_id": transcript_db_id
        },
        "properties": {
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }
            ],
            "Project": {
                "relation": {
                    "id": project_id
                }
            },
            "Language": {
                "type": "select",
                "select": {
                    "name": lang
                }
            }
        },
        "children": blocks,
    }

    response = requests.post(url, json=payload, headers=HEADERS)

    return response.json()["id"]


def _parse_event(start_duration: str) -> Tuple[int, int]:
    """Parse HH:MM:SS.MS/HH:MM:SS.MS into start and duration.

    Return:
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

    start, duration = [s.strip() for s in start_duration.split("/")]

    start_ms = _to_milliseconds(time.fromisoformat(start))
    finish_ms = _to_milliseconds(time.fromisoformat(duration))

    return start_ms, finish_ms - start_ms


def _unparse_event(event: Event) -> str:
    start_ms = event.time_ms
    finish_ms = event.time_ms + event.duration_ms

    def _ms_to_iso_time(ms: int) -> str:
        t = datetime.fromtimestamp(ms / 1000.0).time()
        return t.isoformat()

    return f"{_ms_to_iso_time(start_ms)}/{_ms_to_iso_time(finish_ms)}"


def _get_blocks_from_event(event: Event) -> List[Dict]:
    text = {
        "type": "text",
        "text": {
            "content": _unparse_event(event)
        }
    }
    header = {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [text]
        },
    }
    paragraphs = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": chunk}
                    }
                ]},
        }
        for chunk in event.chunks
    ]

    return [header, *paragraphs]
