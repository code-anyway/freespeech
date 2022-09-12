from tempfile import TemporaryDirectory

import ffmpeg
import pytest

from freespeech.client import chat, client, tasks, transcript
from freespeech.lib.storage import obj
from freespeech.types import Error, Transcript


@pytest.mark.asyncio
async def test_transcribe(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    message = (
        "Transcribe https://www.youtube.com/watch?v=bhRaND9jiOA "
        "in English using Machine B"
    )
    response = await chat.ask(message=message, intent=None, state={}, session=session)

    assert (
        response.message == "Transcribing https://www.youtube.com/watch?v=bhRaND9jiOA"
        " with Machine B in en-US. Watch this space!"
    )

    if isinstance(response, Error):
        assert False, response.message
    result = await tasks.future(response, session)
    if isinstance(result, Error):
        assert False, result.message

    assert isinstance(result, Transcript)
    assert result.events


@pytest.mark.asyncio
async def test_translate(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    doc = "https://docs.google.com/document/d/1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/"  # noqa: E501
    message = f"Translate {doc} to Ukrainian"

    task = await chat.ask(message=message, intent=None, state={}, session=session)
    assert task.message == f"Translating {doc} to uk-UA. Hold on!"

    if isinstance(task, Error):
        assert False, task.message

    result = await tasks.future(task, session)
    if isinstance(result, Error):
        assert False, result.message

    transcript_ua = result
    assert transcript_ua.lang == "uk-UA"
    assert transcript_ua.events


@pytest.mark.asyncio
async def test_synthesize(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    test_doc = "https://docs.google.com/document/d/1Oexfd27oToEWyxj9g7YCp3IYHqjYO8US0RtnoP32fXU/edit#"  # noqa: E501

    test_message = f"Dub {test_doc}"

    task = await chat.ask(message=test_message, intent=None, state={}, session=session)
    if isinstance(task, Error):
        assert False, task.message
    assert task.message == f"Dubbing {test_doc}. Stay put!"

    result = await tasks.future(task, session)
    if isinstance(result, Error):
        assert False, result.message

    transcript_dubbed = result
    assert transcript_dubbed.video

    load_response = await transcript.load(
        source=test_doc, method="Google", lang=None, session=session
    )
    old_transcript = await tasks.future(load_response, session)
    assert isinstance(old_transcript, Transcript)

    assert transcript_dubbed.video != old_transcript.video

    # cropping

    test_doc = "https://docs.google.com/document/d/1krVxccWUgK_958WS9W_BWG5YwCOqqKCkJRbZWjXhbuE/edit"  # noqa: E501

    test_message = f"Dub {test_doc}"

    task = await chat.ask(message=test_message, intent=None, state={}, session=session)
    if isinstance(task, Error):
        assert False, task.message
    assert task.message == f"Dubbing {test_doc}. Stay put!"

    result = await tasks.future(task, session)
    if isinstance(result, Error):
        assert False, result.message

    with TemporaryDirectory() as tmp_dir:
        transcript_str = await obj.get(
            obj.storage_url(str(result.video)), dst_dir=tmp_dir
        )
        assert float(
            ffmpeg.probe(transcript_str).get("format", {}).get("duration", None)
        ) == pytest.approx(1.36, 0.1)
