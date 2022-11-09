from tempfile import TemporaryDirectory

import ffmpeg
import pytest

from freespeech.client import chat, client, tasks, transcript
from freespeech.lib import hash, media, speech
from freespeech.lib.storage import obj
from freespeech.types import Error, Transcript, Voice

AUDIO_BLANK = "tests/lib/data/ask/audio-blank-blanked.wav"
AUDIO_BLANK_SYNTHESIZED = "tests/lib/data/ask/audio-blank-synthesized.wav"
AUDIO_FILL = "tests/lib/data/ask/audio-fill-filled.wav"
AUDIO_FILL_SYNTHESIZED = "tests/lib/data/ask/audio-fill-synthesized.wav"


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
async def test_transcribe_machine_d(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    message = (
        "Transcribe https://www.youtube.com/watch?v=N9B59PHIFbA "
        "in English using Machine D"
    )
    response = await chat.ask(message=message, intent=None, state={}, session=session)

    assert (
        response.message == "Transcribing https://www.youtube.com/watch?v=N9B59PHIFbA"
        " with Machine D in en-US. Watch this space!"
    )

    if isinstance(response, Error):
        assert False, response.message
    result = await tasks.future(response, session)
    if isinstance(result, Error):
        assert False, result.message

    assert isinstance(result, Transcript)
    assert len(result.events) == 12


@pytest.mark.asyncio
async def test_transcribe_from_gdoc_srt(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    message = (
        "Transcribe https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing "  # noqa: E501
        "in English using SRT"
    )
    response = await chat.ask(message=message, intent=None, state={}, session=session)

    assert (
        response.message == "Transcribing "
        "https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing"  # noqa: E501
        " with SRT in en-US. Watch this space!"
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


@pytest.mark.asyncio
async def test_synthesize_crop(mock_client, monkeypatch) -> None:
    monkeypatch.setattr(client, "create", mock_client)
    session = mock_client()

    test_doc = "https://docs.google.com/document/d/1HpH-ZADbAM8AzluFWO8ZTOkEoRobAvQ13rrCsK6SU-U/edit?usp=sharing"  # noqa: E501

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
        ) == pytest.approx(11.4, 0.12)


@pytest.mark.asyncio
async def test_synthesize_blank(mock_client, monkeypatch) -> None:
    async def synthesize_events(*args, **kwargs):
        return [
            AUDIO_BLANK_SYNTHESIZED,
            [
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            ],
            [
                ("blank", 0, 2000),
                ("event", 2000, 6329),
                ("blank", 6329, 15000),
                ("event", 15000, 20116),
            ],
        ]

    monkeypatch.setattr(client, "create", mock_client)
    monkeypatch.setattr(speech, "synthesize_events", synthesize_events)
    session = mock_client()

    test_doc = "https://docs.google.com/document/d/1CvjpOs5QEe_mmAc5CEGRVNV68qDjdQipCDb2ge6OIn4/edit?usp=sharing"  # noqa: E501

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
        downmixed_audio = await media.multi_channel_audio_to_mono(
            transcript_str, tmp_dir
        )
        assert hash.file(str(downmixed_audio)) == hash.file(AUDIO_BLANK)


@pytest.mark.asyncio
async def test_synthesize_fill(mock_client, monkeypatch) -> None:
    async def synthesize_events(*args, **kwargs):
        return [
            AUDIO_FILL_SYNTHESIZED,
            [
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            ],
            [
                ("blank", 0, 2000),
                ("event", 2000, 9239),
                ("blank", 9239, 15000),
                ("event", 15000, 21245),
            ],
        ]

    monkeypatch.setattr(client, "create", mock_client)
    monkeypatch.setattr(speech, "synthesize_events", synthesize_events)
    session = mock_client()

    test_doc = "https://docs.google.com/document/d/11WOfJZi8pqpj7_BLPy0uq9h1R0f_n-dJ11LPOBvPtQA/edit?usp=sharing"  # noqa: E501

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
        downmixed_audio = await media.multi_channel_audio_to_mono(transcript_str, ".")
        assert hash.file(str(downmixed_audio)) == hash.file(AUDIO_FILL)
