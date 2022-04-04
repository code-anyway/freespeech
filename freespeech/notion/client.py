import logging
import requests


from datetime import time, datetime
from typing import Any, Dict, List, Tuple


from freespeech import env
from freespeech.types import Event, Transcript


logger = logging.getLogger(__name__)


HEADERS = {
    "Accept": "application/json",
    "Notion-Version": "2022-02-22",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {env.get_notion_token()}"
}


def get_pages(database_id: str, page_size: int = 100) -> List[str]:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    page_ids = []
    payload = {
        "page_size": page_size
    }
    while True:
        response = requests.request("POST", url, json=payload, headers=HEADERS)
        data = response.json()

        page_ids += [
            page["id"]
            for page in data["results"]
            if not page["archived"]
        ]

        if data["has_more"]:
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return page_ids


def get_page_info(_id: str) -> Dict:
    """Get page information.

    Args:
        _id: id of a page.

    Returns:
        Dict with page info.
        Note: it doesn't return page content. Use `get_child_blocks`
        for that.
    """
    url = f"https://api.notion.com/v1/pages/{_id}"
    response = requests.request("GET", url, headers=HEADERS)
    return response.json()


def get_page_blocks(_id: str) -> Dict:
    """Get child blocks for a page.

    Args:
        _id: id of a page.

    Returns:
        Dict with child block content.
    """
    url = f"https://api.notion.com/v1/blocks/{_id}/children"
    response = requests.request("GET", url, headers=HEADERS)
    return response.json()


def get_page_properties(page: Dict) -> Dict[str, Any]:
    properties = {
        property: parse_property_value(value)
        for property, value in page["properties"].items()
    }

    return properties


def _get_pain_text(rich_text: List[Dict]) -> str:
    return "\n".join(item["plain_text"] for item in rich_text)


def _parse_event(start_duration: str) -> Tuple[int, int]:
    """Parse HH:MM:SS.MS/HH:MM:SS.MS into start and duration.

    Return:
        Event start time and duration in milliseconds.
    """

    # TODO (astaff): couldnt find a sane way to do that
    # other than parsing it as datetime from a custom
    # ISO format that ingores date. Hence this.
    def _to_milliseconds(t: time):
        return \
            t.hour * 60 * 60 * 1_000 + \
            t.minute * 60 * 1_000 + \
            t.second * 1_000 + \
            t.microsecond // 1_000

    start, duration = [s.strip() for s in start_duration.split("/")]

    start_ms = _to_milliseconds(time.fromisoformat(start))
    finish_ms = _to_milliseconds(time.fromisoformat(duration))

    return start_ms, finish_ms - start_ms


def get_events(page_blocks: Dict) -> List[Event]:
    """Generate transcript events by parsing Notion's page.

    Args:
        page_blocks: valid JSON from Notion's GET block API call.
        lang: transcript language. i.e. en-US.

    Returns:
        Parsed trasncript.
    """
    HEADINGS = [
        "heading_1",
        "heading_2",
        "heading_3",
    ]

    results = (r for r in page_blocks["results"] if not r["archived"])
    events = dict()

    for result in results:
        _type = result["type"]
        value = result[_type]
        if _type in HEADINGS:
            key = _parse_event(_get_pain_text(value["rich_text"]))
            events[key] = events.get(key, [])
        elif _type == "paragraph":
            if key is None:
                logger.warning(f"Paragraph without timestamp: {value}")
            events[key].append(_get_pain_text(value["rich_text"]))

    events = [
        Event(
            time_ms=time_ms,
            duration_ms=duration_ms,
            chunks=chunks
        )
        for (time_ms, duration_ms), chunks in events.items()
    ]

    return events


def get_transcript(page_id: str) -> List[Transcript]:
    properties = get_page_properties(get_page_info(page_id))
    transcript = Transcript(
        _id=page_id,
        lang=properties["title"],
        events=get_events(page_blocks=get_page_blocks(page_id))
    )

    return transcript


def get_all_transcripts(main_page_id: str) -> List[Transcript]:
    """Get all Transcripts from the main page.

    Args:
        main_page_id: id of the task's main page from Notion API.

    Returns:
        List of transcripts parsed from child pages
        of the task's main page.
    """

    blocks = get_page_blocks(main_page_id)
    child_pages = (
        res["id"]
        for res in blocks["results"]
        if res["type"] == "child_page" and not res["archived"]
    )

    transcripts = [
        get_transcript(child_page_id)
        for child_page_id in child_pages
    ]

    return transcripts


def parse_property_value(value: Dict) -> str | List[str]:
    _type = value["type"]

    match _type:
        case "multi_select":
            return [v["name"] for v in value[_type]]
        case "select":
            return value[_type]["name"]
        case "title":
            return "\n".join(
                v["plain_text"]
                for v in value[_type]
            )
        case _:
            return value[_type]


def _event_to_text(event: Event) -> str:
    start_ms = event.time_ms
    finish_ms = event.time_ms + event.duration_ms

    def _ms_to_iso_time(ms: int) -> str:
        t = datetime.fromtimestamp(ms / 1000.0).time()
        return t.isoformat()

    return f"{_ms_to_iso_time(start_ms)}/{_ms_to_iso_time(finish_ms)}"


def _get_blocks_from_event(event: Event) -> List[Dict]:
    header = {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": _event_to_text(event)
                    }
                }
            ]
        }
    }
    paragraphs = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": chunk
                        }
                    }
                ]
            }
        }
        for chunk in event.chunks
    ]

    return [header, *paragraphs]


def add_transcript(parent: str, lang: str, events: List[Event]) -> Transcript:
    url = "https://api.notion.com/v1/pages"
    blocks = [_get_blocks_from_event(event) for event in events]

    # flatten blocks
    blocks = sum(blocks, [])

    payload = {
        "parent": {
            "type": "page_id",
            "page_id": parent
        },
        "properties": {
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": lang
                    }
                }
            ]
        },
        "children": blocks
    }

    response = requests.request(
        "POST",
        url,
        json=payload,
        headers=HEADERS
    ).json()

    return get_transcript(response["id"])
