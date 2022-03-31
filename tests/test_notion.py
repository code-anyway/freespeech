import pytest
import uuid


from freespeech.notion import client
from freespeech.types import Transcript, Event
from freespeech.notion.types import Document, Content


TEST_DOCUMENT = "https://www.notion.so/Announcer-s-test-fe999aa7a53a448a8b6f3dcfe07ab434"  # noqa: E501
TEST_DATABASE = "https://www.notion.so/4d8d51229d854929b193a13604bf47dc?v=9e721e82784044808b86004478928d3f"  # noqa: E501
TEST_DOCUMENT_FOR_UPDATES = "https://www.notion.so/Dummy-553e3db2376341a7ae8abd4faa93131d"


def test_get_all_documents():
    assert client.get_documents(TEST_DATABASE) == ["uuid1", "uuid2"]


def test_get_documents_by_property():
    assert client.get_documents(TEST_DATABASE, stage="Transcribe") == ["uuid2"]
    with pytest.raises(AttributeError, match=r"Invalid property: foo"):
        client.get_documents(TEST_DATABASE, foo="bar")


def test_get_document():
    doc = client.get_document(TEST_DOCUMENT)
    assert doc.title == "Announcer's test"


def test_parse_transcript():
    doc = client.get_document(TEST_DOCUMENT)
    transcript = client.parse_transcript(doc["Transcript"])
    assert transcript == Transcript(
        lang="en-US",
        events=[
            Event(
                time_ms=1000,
                duration_ms=2000,
            ),
            Event(
                time_ms=4000,
                duration_ms=2000
            )
        ]
    )


def test_create_update_delete():
    title = str(uuid.uuid4())
    _id = client.create_document(TEST_DATABASE, title=title)
    empty_document = client.get_document(_id)

    assert empty_document.title == title

    new_document = Document(
        title=title,
        properties={
            "Source Language": "uk-UK"
        },
        content=[
            Content(
                title="1",
                content=[
                    Content(title="1.1", text="TextA"),
                    Content(title="1.2", text="TextB")
                ]
            ),
            Content(
                title="2",
                text="TextC"
            ),
        ]
    )

    client.update_document(_id, new_document)
    assert client.get_document(_id) == new_document


def test_update_transcript():
    transcription = client.update_transcript(TEST_DOCUMENT, "Tanslation")
    assert transcription == Transcript(
        lang="en-US",
        events=[
            Event(
                time_ms=1000,
                duration_ms=2000,
            ),
            Event(
                time_ms=4000,
                duration_ms=2000
            )
        ]
    )
