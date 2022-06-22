import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Sequence, Tuple

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
    original_audio_level: float
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
def gdocs_client(
    credentials: service_account.Credentials,
) -> googleapiclient.discovery.Resource:
    service = googleapiclient.discovery.build("docs", "v1", credentials=credentials)
    try:
        yield service
    finally:
        # Some client libraries are leaving SSL connections unclosed
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        service._http.http.close()


@contextmanager
def drive_client(
    credentials: service_account.Credentials,
) -> googleapiclient.discovery.Resource:
    service = googleapiclient.discovery.build("drive", "v3", credentials=credentials)
    try:
        yield service
    finally:
        # Some client libraries are leaving SSL connections unclosed
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        service._http.http.close()


def get_credentials(scopes: List[str]) -> service_account.Credentials:
    return service_account.Credentials.from_service_account_file(
        env.get_service_account_file(),
        scopes=scopes,
    )


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
    credentials = get_credentials(
        scopes=["https://www.googleapis.com/auth/documents.readonly"]
    )

    with gdocs_client(credentials) as client:
        documents = client.documents()
        document = documents.get(documentId=document_id).execute()

    return _read_structural_elements(document.get("body").get("content"))


def parse_properties(text: str) -> Page:
    """Parses the properties of a transcript from the input string.

    Args:
        text: a string containing the properties for a transcript.

    Returns:
        a Page object.
    """
    page_attributes = [
        "origin",
        "language",
        "voice",
        "clip_id",
        "method",
        "original_audio_level",
        "video",
    ]
    properties = dict(
        re.findall(rf"({'|'.join(page_attributes)}):\s*(.*)$", text, flags=re.M)
    )

    keys = properties.keys()
    for attribute in page_attributes:
        if attribute not in keys and attribute != "video":
            raise TypeError(f"{attribute} must be defined")

    properties["original_audio_level"] = float(properties["original_audio_level"])
    properties["video"] = None if "video" not in keys else properties["video"] or None

    return Page(**properties)


def parse(text: str) -> Tuple[Page, Sequence[Event]]:
    match = transcript.timecode_parser.search(text)

    if not match:
        raise ValueError("Invalid document content")

    transcript_start = match.start()
    properties = text[:transcript_start]
    page = parse_properties(properties)

    events = transcript.parse_events(text=text[transcript_start:])

    return page, events


def share_with_all(document_id: str):
    permission = {
        "type": "anyone",
        "role": "writer",
    }
    with drive_client(
        get_credentials(scopes=["https://www.googleapis.com/auth/drive"])
    ) as service:
        service.permissions().create(
            fileId=document_id,
            body=permission,
            fields="id",
        ).execute()


def create(title: str, page: Page, events: Sequence[Event]) -> str:
    text = text_from_properties_and_events(page, events)
    body = {
        "title": title,
    }
    requests = [
        {
            "insertText": {
                "location": {
                    "index": 1,
                },
                "text": text,
            }
        },
    ]

    credentials = get_credentials(scopes=["https://www.googleapis.com/auth/documents"])

    with gdocs_client(credentials) as client:
        documents = client.documents()
        document = documents.create(body=body).execute()
        _id = document.get("documentId")

        client.documents().batchUpdate(
            documentId=_id, body={"requests": requests}
        ).execute()

    # TODO (astaff): introduce permissions control.
    share_with_all(_id)

    return f"https://docs.google.com/document/d/{_id}/edit#"


def text_from_properties_and_events(page: Page, events: Sequence[Event]) -> str:
    output = ""

    # putting up properties
    properties = vars(page)
    for property, value in properties.items():
        attribute_value = " " + str(value) if value else ""
        output += f"{property}:{attribute_value}\n"

    # putting up events
    for event in events:
        output += "\n"
        output += (
            transcript.unparse_time_interval(
                event.time_ms, event.duration_ms, event.voice
            )
            + "\n"
        )
        output += "\n".join(event.chunks) + "\n"

    return output
