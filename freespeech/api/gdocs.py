import re
from contextlib import contextmanager
from typing import Any

import googleapiclient.discovery
from google.oauth2 import service_account

from freespeech import env


def _read_paragraph_element(element):
    """Returns the text in the given ParagraphElement.

    Args:
        element: a ParagraphElement from a Google Doc.
    """
    text_run = element.get("textRun")
    if not text_run:
        return ""
    return text_run.get("content")


def _read_structural_elements(elements):
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
