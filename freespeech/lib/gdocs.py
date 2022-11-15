import logging
import re
from contextlib import contextmanager
from dataclasses import replace
from typing import List, Tuple

import google.auth
import googleapiclient.discovery
from google.oauth2 import service_account

from freespeech.lib import ssmd
from freespeech.lib.transcript import (
    events_to_srt,
    parse_transcript,
    render_events,
    render_properties,
    render_transcript,
)
from freespeech.types import Transcript, TranscriptFormat

logger = logging.getLogger(__name__)


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
    credentials, _ = google.auth.default(scopes=scopes)
    return credentials


def extract(url: str) -> Tuple[str, str]:
    """Extracts title and text contents of Google Docs document.

    Args:
        url: Google Docs document URL.

    Returns:
        A tuple containing title and plain text with contents of the document.
    """
    try:
        document_id, *_ = re.findall(r"\/document\/d\/([a-zA-Z0-9-_]+)", url)
    except ValueError as e:
        raise ValueError(f"Invalid URL: {url}") from e
    credentials = get_credentials(
        scopes=["https://www.googleapis.com/auth/documents.readonly"]
    )

    try:
        with gdocs_client(credentials) as client:
            documents = client.documents()
            document = documents.get(documentId=document_id).execute()

        return document.get("title"), _read_structural_elements(
            document.get("body").get("content")
        )
    except googleapiclient.errors.HttpError as e:
        match e.status_code:
            case 403:
                raise PermissionError(e.error_details) from e
            case 404:
                raise RuntimeError(e.error_details) from e
            case _:
                raise e


def load(url: str) -> Transcript:
    """Loads transcript from Google Docs document.

    Args:
        url: Google Docs document URL.

    Return:
        Instance of Transcript initialized from the document.
    """
    title, text = extract(url)
    transcript = parse_transcript(text)
    return replace(transcript, title=title)


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


def create(source: Transcript, format: TranscriptFormat) -> str:
    manifest = f"{render_properties(source)}\nformat: {format}\n\n"
    match format:
        case "SSMD":
            return create_from_text(
                title=source.title, text=manifest + render_events(source.events)
            )
        case "SSMD-NEXT":
            return create_from_text(
                title=source.title,
                text=manifest + ssmd.render(list(source.events)),
            )
        case "SRT":
            return create_from_text(
                title=source.title, text=manifest + events_to_srt(source.events)
            )


def create_from_text(title: str | None, text: str) -> str:
    title = title or "Untitled"

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

        documents.batchUpdate(documentId=_id, body={"requests": requests}).execute()

    # TODO (astaff): introduce permissions control.
    share_with_all(_id)

    return f"https://docs.google.com/document/d/{_id}/edit#"
