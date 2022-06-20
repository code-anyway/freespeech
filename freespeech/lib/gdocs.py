from argparse import ArgumentError
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from tracemalloc import start
from typing import Any, Sequence, Tuple

import googleapiclient.discovery
from google.oauth2 import service_account

from freespeech import env
from freespeech.lib import transcript
from freespeech.types import Character, Event, Language, Source

logger = logging.getLogger(__name__)


@dataclass
class Page:
    origin: str
    language: Language
    voice: Character
    clip_id: str
    method: Source
    original_audio_level: int
    video: str | None


def _read_paragraph_element(element):
    """Returns the text in the given ParagraphElement.

    Args:
        element: a ParagraphElement from a Google Doc.
    """
    text_run = element.get("textRun")
    if not text_run:
        return ""
    return text_run.get("content")


def _read_structural_elements(elements) -> str:
    """Recurses through a list of Structural Elements to read a document's text.

    Text may be in nested elements.

    Args:
        elements: a list of Structural Elements.
    """
    text = ""
    for value in elements:
        if "paragraph" in value:
            elements = value.get("paragraph").get("elements")
            for elem in elements:
                text += _read_paragraph_element(elem)
        elif "table" in value:
            # The text in table cells are in nested Structural Elements
            # and tables may be nested.
            table = value.get("table")
            for row in table.get("tableRows"):
                cells = row.get("tableCells")
                for cell in cells:
                    text += _read_structural_elements(cell.get("content"))
        elif "tableOfContents" in value:
            # The text in the TOC is also in a Structural Element.
            toc = value.get("tableOfContents")
            text += _read_structural_elements(toc.get("content"))
    return text


@contextmanager
def gdocs_client(credentials: service_account.Credentials) -> Any:
    service = googleapiclient.discovery.build("docs", "v1", credentials=credentials)
    try:
        yield service
    finally:
        # Some client libraries are leaving SSL connections unclosed
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        service._http.http.close()


def extract(url: str) -> str:
    """Extracts text contents of Google Docs document.

    Args:
        url: Google Docs document URL.

    Returns:
        Plain text with contents of the document.
    """
    try:
        document_id, *_ = re.findall(r"\/document\/d\/([a-zA-Z0-9-_]+)", url)
    except ValueError as e:
        raise ValueError(f"Invalid URL: {url}") from e
    credentials = service_account.Credentials.from_service_account_file(
        env.get_service_account_file(),
        scopes=["https://www.googleapis.com/auth/documents.readonly"],
    )

    with gdocs_client(credentials) as client:
        documents = client.documents()
        document = documents.get(documentId=document_id).execute()

    return _read_structural_elements(document.get("body").get("content"))


def parse_properties(text: str) -> Page:
    """Parses the properties of a transcript from the input string.

    Args:
        text: a tring containing the properties for a transcript.

    Returns:
        a Page object.
    """

    def find_property(attribute: str, text: str):
        attribute_in_doc = attribute.replace("_", " ")
        match_object = re.search(f"(?<={attribute_in_doc}: ).*", text, flags=re.I)

        if not match_object:
            if attribute != "video":
                raise TypeError(f"{attribute_in_doc} must be defined")
            return None
        if attribute == "original_audio_level":
            return int(match_object[0])

        return match_object[0]

    page_attributes = vars(Page)["__match_args__"]
    properties = [find_property(attr, text) for attr, in zip(page_attributes)]

    return Page(*properties)


def parse(text: str) -> Tuple[Page, Sequence[Event]]:
    blocks = transcript.timecode_parser.split(text)

    head, *paragraphs = blocks[:: transcript.timecode_parser.groups + 1]
    page = parse_properties(head)

    timestamps = blocks[1 :: transcript.timecode_parser.groups + 1]
    lines: Sequence[str] = sum([list(t) for t in zip(timestamps, paragraphs)], [])
    events = transcript.parse_events(lines)

    return page, events


def from_properties_and_events(page: Page, events: Sequence[Event]) -> str:
    output = ""

    # putting up properties
    properties = vars(page)
    for property, value in properties.items():
        attribute_in_doc = " ".join(word.capitalize() for word in property.split("_"))
        attribute_value = " " + str(value) if value else ""
        output += f"{attribute_in_doc}:{attribute_value}\n"

    # putting up events
    output += "\n"
    for event in events:
        output += transcript.unparse_time_interval(
            event.time_ms, event.duration_ms, event.voice
        )
        output += "".join(event.chunks)

    return output
