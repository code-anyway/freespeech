import logging
from datetime import datetime, time
from typing import Dict, List, Tuple, Literal

import requests

from freespeech import env
from freespeech.types import Event, Language

logger = logging.getLogger(__name__)


QueryOperator = Literal["greater_than", "equals", "after", "any"]


NOTION_MAX_PAGE_SIZE = 100

HEADERS = {
    "Accept": "application/json",
    "Notion-Version": "2022-02-22",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {env.get_notion_token()}",
}


def query(database_id: str,
          property_name: str,
          property_type: str,
          operator: QueryOperator,
          value: str | Dict) -> List[str]:
    """Get all pages where property matches the expression."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    page_ids = []

    # How filtering in Notion API works:
    # https://developers.notion.com/reference/post-database-query-filter#rollup-filter-condition  # noqa E501
    payload: Dict[str, Dict | int] = {
        "filter": {
            "property": property_name,
            property_type: {
                operator: value
            }
        },
    }
    payload["page_size"] = NOTION_MAX_PAGE_SIZE

    # TODO (astaff): There must be a more pythonic and reusable way
    # to handle pagination it REST APIs but I can't quite express it yet.
    while True:
        response = requests.request("POST", url, json=payload, headers=HEADERS)
        data = response.json()

        if data["object"] == "error":
            raise RuntimeError(data["message"])

        page_ids += [
            page["id"] for page in data["results"]
            if not page["archived"]]

        if data["has_more"]:
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return page_ids


def get_page_properties(page_id: str) -> Dict:
    """Get page information.

    Args:
        page_id: id of a page.

    Returns:
        Dict with page info.
        Note: it doesn't return page content. Use `get_child_blocks`
        for that.
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.get(url, headers=HEADERS)
    page = response.json()

    properties = {
        property: _parse_value(value)
        for property, value in page["properties"].items()
    }

    return properties


def _parse_value(value: Dict,
                 value_type: str | None = None
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
            return "\n".join(v["plain_text"] for v in value[_type])
        case "heading_1" | "heading_2" | "heading_3" | "paragraph":
            return _parse_value(value[_type], value_type="rich_text")
        case _:
            return value[_type]


def get_transcript(page_id: str) -> List[Event]:
    """Parse Notion's page and generate transcript.

    Args:
        page_id: Notion page ID.

    Returns:
        Transcript represented as list of speech events.
    """
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=HEADERS)

    blocks = response.json()
    results = (r for r in blocks["results"] if not r["archived"])
    events: Dict[Tuple[int, int], List[str]] = dict()

    HEADINGS = ["heading_1", "heading_2", "heading_3"]

    for result in results:
        _type = result["type"]
        if _type in HEADINGS:
            value = _parse_value(result)
            assert isinstance(value, str)
            key = parse_time_interval(value)
            events[key] = events.get(key, [])
        elif _type == "paragraph":
            value = _parse_value(result)
            if not key:
                logger.warning(f"Paragraph without timestamp: {value}")
            assert isinstance(value, str)
            events[key].append(value)

    return [Event(time_ms=time_ms,
                  duration_ms=duration_ms,
                  chunks=chunks)
            for (time_ms, duration_ms), chunks in events.items()]


def get_updated_pages(db_id: str, timestamp: str) -> List[str]:
    """Get all pages that were updated after `timestamp`."""
    raise NotImplementedError()


def get_transcripts(database_id: str, url: str) -> Dict[Language, List[Event]]:
    """Get all transcripts for a video url.

    Args:
        database_id: id of a Notion database containing transcripts.
        url: url of a video the transcripts are associated with.

    Returns:
        A dict with transcript's language as a key
        and speech events as a value.
    """

    page_ids = query(
        database_id=database_id,
        property_name="Origin",
        property_type="rollup",
        operator="any",
        value={
            "rich_text": {
                "equals": url
            }
        }
    )

    transcripts = {
        get_page_properties(_id)["Language"]: get_transcript(_id)
        for _id in page_ids
    }

    return transcripts


def add_transcript(project_database_id: str,
                   transcript_database_id: str,
                   video_url: str,
                   lang: str,
                   title: str,
                   events: List[Event]) -> str:
    url = "https://api.notion.com/v1/pages"

    project_id, *tail = query(database_id=project_database_id,
                              property_name="Video",
                              property_type="url",
                              operator="equals",
                              value=video_url)

    if tail:
        logger.warning(
            f"Multiple projects with the same Video url in "
            f"{project_database_id}: {[project_id] + tail}")

    # Flatten event blocks
    blocks: List[Dict] = sum(
        [render_event(event) for event in events], [])

    payload = {
        "parent": {
            "type": "database_id",
            "database_id": transcript_database_id
        },
        "properties": {
            "Name": {
                "title": [{
                    "type": "text",
                    "text": {
                        "content": title
                    }
                }],
            },
            "Project": {
                "relation": [
                    {
                        "id": project_id
                    }
                ]
            },
            "Language": {
                "select": {
                    "name": lang
                }
            }
        },
        "children": blocks,
    }

    response = requests.post(url, json=payload, headers=HEADERS)

    return response.json()["id"]


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
    """Generates list of Notion blocks representing an speech event."""
    text = {
        "type": "text",
        "text": {
            "content": unparse_time_interval(event.time_ms, event.duration_ms)
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
