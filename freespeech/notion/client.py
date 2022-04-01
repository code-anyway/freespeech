import logging
import requests


from datetime import time
from typing import Dict, List, Tuple


from freespeech import env
from freespeech.types import Event, Language, Transcript


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


def get_page(_id: str) -> Dict:
    url = f"https://api.notion.com/v1/pages/{_id}"
    response = requests.request("GET", url, headers=HEADERS)
    return response.json()


def get_blocks(_id: str) -> Dict:
    url = f"https://api.notion.com/v1/blocks/{_id}"
    response = requests.request("GET", url, headers=HEADERS)
    return response.json()


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
    duration_ms = _to_milliseconds(time.fromisoformat(duration))

    return start_ms, duration_ms


def parse_transcript(block: Dict, lang: Language) -> Transcript:
    """Generates Transcript by parsing Notion's block.

    Args:
        block: valid JSON from Notion's GET block API call.
        lang: transcript language. i.e. en-US.

    Returns:
        Parsed trasncript.
    """
    HEADINGS = [
        "heading_1",
        "heading_2",
        "heading_3",
    ]

    results = (r for r in block["results"] if not r["archived"])
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

    transcript = Transcript(
        lang=lang,
        events=events
    )

    return transcript


def get_transcripts(_id: str) -> List[Transcript]:
    """Get Transcripts from the main page.
    
    Args:
        _id: id of the task's main page from Notion API.

    Returns:
        List of transcripts parsed from child pages
        of the task's main page.
    """