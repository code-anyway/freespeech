import pytest

from freespeech.client import chat, client, tasks, transcript
from freespeech.types import Error, Transcript


@pytest.mark.asyncio
async def test_transcribe(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    message = (
        "Transcribe https://www.youtube.com/watch?v=N9B59PHIFbA "
        "in English using Machine A"
    )
    response = await chat.ask(message=message, intent=None, state={}, session=session)
    if isinstance(response, Error):
        assert False, response.message
    result = await tasks.future(response)
    if isinstance(result, Error):
        assert False, result.message
    assert result.message.startswith("Here you are: ")

    load_response = await transcript.load(
        source=result.message[14:], method="Google", lang=None, session=session
    )
    load_result = await tasks.future(load_response)
    if isinstance(load_result, Error):
        assert False, load_result.message
    assert load_result.events


@pytest.mark.asyncio
async def test_translate(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    message = (
        "Translate https://docs.google.com/document/d/"
        "1FbV0eW4Q-yKWYjPkMRCrGd2yD78n7MtswVmN9LSo4mA/edit to Ukrainian"
    )

    response = await chat.ask(message=message, intent=None, state={}, session=session)
    if isinstance(response, Error):
        assert False, response.message
    result = await tasks.future(response)
    if isinstance(result, Error):
        assert False, result.message
    assert result.message.startswith("Here you are: ")

    load_response = await transcript.load(
        source=result.message[14:], method="Google", lang=None, session=session
    )
    load_result = await tasks.future(load_response)
    if isinstance(load_result, Error):
        assert False, load_result.message
    assert load_result.events
    assert (
        load_result.events[0]
        .chunks[0]
        .startswith("Якщо ви можете згадати")
    )


@pytest.mark.asyncio
async def test_synthesize(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()
    test_doc = (
        "https://docs.google.com/document/d/"
        "1Oexfd27oToEWyxj9g7YCp3IYHqjYO8US0RtnoP32fXU/edit#"
    )

    test_message = f"Dub {test_doc}"

    response = await chat.ask(
        message=test_message, intent=None, state={}, session=session
    )
    if isinstance(response, Error):
        assert False, response.message
    result = await tasks.future(response)
    if isinstance(result, Error):
        assert False, result.message
    assert result.message.startswith("Here you are: ")
    new_video_url = result.message[14:]

    load_response = await transcript.load(
        source=test_doc, method="Google", lang=None, session=session
    )
    old_transcript = await tasks.future(load_response)
    assert isinstance(old_transcript, Transcript)

    assert new_video_url != old_transcript.video
