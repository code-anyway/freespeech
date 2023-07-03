import asyncio
from typing import List, Tuple

import pytest

from freespeech import telegram


class Media:
    def __init__(self, mime_type):
        self.document = Document(mime_type)


class Document:
    def __init__(self, mime_type):
        self.mime_type = mime_type


class SubMessage:
    def __init__(self, src: str):
        self.src = src

    async def download_media(self, type):
        with open(self.src, "rb") as file:
            return file.read()


class Message(object):
    def __init__(self, text, submessage: SubMessage | None = None, mime_type: str = ""):
        self.raw_text = text
        self.replies: List[Tuple[Message, List[str], bytes]] = []
        self.sender_id = 0
        self.sender = None
        self.media = None if mime_type == "" else Media(mime_type)
        self.message = submessage

    async def reply(
        self, message, buttons=None, file=None, force_document=None, link_preview=None
    ):
        self.replies.append((message, buttons, file))
        return self

    async def read(self, timeout_sec=5):
        while not self.replies:
            await asyncio.sleep(0.1)
            timeout_sec -= 0.1
            if timeout_sec <= 0:
                raise TimeoutError("No reply received")
        return self.replies.pop()


async def initiate(url):
    message = Message(url)
    await telegram.dispatch(0, message)
    text, buttons, file = await message.read()
    assert (
        text
        == "Would you like to translate, dub, or download the transcript as SRT or TXT?"  # noqa E501
    )  # noqa E501
    assert [button.text for button in buttons] == ["Translate", "Dub", "SRT", "TXT"]
    assert file is None
    return message


@pytest.mark.asyncio
async def test_telegram():
    message = Message("https://youtu.be/bhRaND9jiOA")

    await telegram.dispatch(0, message)
    text, buttons, file = await message.read()
    assert text == "Create transcript using Subtitles or Speech Recognition?"
    assert [button.text for button in buttons] == ["Subtitles", "Speech Recognition"]
    assert file is None

    await telegram.dispatch(0, "Subtitles")
    text, buttons, file = await message.read()
    assert text == "Please select *source* language. Or send it as a message."
    assert [button.text for button in buttons] == [
        "EN",
        "UA",
        "ES",
        "FR",
        "DE",
        "PT",
        "TR",
    ]
    assert file is None

    await telegram.dispatch(0, "EN")

    text, buttons, file = await message.read()
    assert text == "What size do you want timed paragraphs to be?"
    assert [button.text for button in buttons] == ["Small", "Medium", "Large", "Auto"]
    await telegram.dispatch(0, "Small")

    text, buttons, file = await message.read()
    assert (
        text == "Sure! Give me 40 seconds to transcribe it in en-US using Subtitles."
    )  # noqa E501
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=180)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None

    url = text[len("Here you are: ") :]
    message = await initiate(url)
    await telegram.dispatch(0, "SRT")
    text, buttons, file = await message.read()
    assert text == "SRT"
    assert buttons is None
    assert file.decode("utf-8").startswith(
        "1\n00:00:00,480 --> 00:00:28,400\none hen two ducks three squawking geese"  # noqa E501
    )  # noqa E501

    message = await initiate(url)
    await telegram.dispatch(0, "TXT")
    text, buttons, file = await message.read()
    assert text == "Plain text"
    assert buttons is None
    assert file.decode("utf-8").startswith(
        "one hen two ducks three squawking geese"  # noqa E501
    )  # noqa E501

    message = await initiate(url)
    await telegram.dispatch(0, "Translate")
    text, buttons, file = await message.read()
    assert text == "Please select *target* language. Or send it as a message."
    assert [button.text for button in buttons] == [
        "EN",
        "UA",
        "ES",
        "FR",
        "DE",
        "PT",
        "TR",
    ]
    assert file is None

    await telegram.dispatch(0, "Russian")  # try full language name
    text, buttons, file = await message.read()
    assert text == "Sure! I'll translate it in about 3 seconds."
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=20)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None

    url = text[len("Here you are: ") :]
    message = await initiate(url)
    await telegram.dispatch(0, "Dub")
    text, buttons, file = await message.read()
    assert text.startswith("Sure! I'll dub it in about")
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=60)
    assert text.startswith("Here you are: https://")
    assert buttons is None
    assert file is None


@pytest.mark.asyncio
async def test_telegram_direct_upload_audio():
    # Test flow with audio file
    AUDIO_SRC = "tests/lib/data/media/2sec.wav"
    message = Message("", SubMessage(AUDIO_SRC), mime_type="audio/wav")

    await telegram.dispatch(0, message)
    text, buttons, file = await message.read()
    assert text == "Create transcript using Speech Recognition?"
    assert [button.text for button in buttons] == ["Yes"]
    assert file is None

    await telegram.dispatch(0, "Yes")
    text, buttons, file = await message.read()
    assert text == "Please select *source* language. Or send it as a message."
    assert [button.text for button in buttons] == [
        "EN",
        "UA",
        "ES",
        "FR",
        "DE",
        "PT",
        "TR",
    ]
    assert file is None

    await telegram.dispatch(0, "EN")
    text, buttons, file = await message.read()
    assert text == "What size do you want timed paragraphs to be?"
    assert [button.text for button in buttons] == ["Small", "Medium", "Large", "Auto"]
    await telegram.dispatch(0, "Small")

    text, buttons, file = await message.read()
    assert text == "Sure! Give me some time to transcribe it in en-US using Machine D."
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=60)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None


@pytest.mark.asyncio
async def test_telegram_direct_upload_video():
    # Test flow with video file
    VIDEO_SRC = "tests/lib/data/media/2sec.mp4"
    message = Message("", SubMessage(VIDEO_SRC), mime_type="video/mp4")

    await telegram.dispatch(0, message)
    text, buttons, file = await message.read()
    assert text == "Create transcript using Speech Recognition?"
    assert [button.text for button in buttons] == ["Yes"]
    assert file is None

    await telegram.dispatch(0, "Yes")
    text, buttons, file = await message.read()
    assert text == "Please select *source* language. Or send it as a message."
    assert [button.text for button in buttons] == [
        "EN",
        "UA",
        "ES",
        "FR",
        "DE",
        "PT",
        "TR",
    ]
    assert file is None

    await telegram.dispatch(0, "EN")
    text, buttons, file = await message.read()
    assert text == "What size do you want timed paragraphs to be?"
    assert [button.text for button in buttons] == ["Small", "Medium", "Large", "Auto"]
    await telegram.dispatch(0, "Small")

    text, buttons, file = await message.read()
    assert (
        text == "Sure! Give me some time to transcribe it in en-US using Machine D."
    )  # noqa E501
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=60)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None

    url = text[len("Here you are: ") :]
    message = await initiate(url)
    await telegram.dispatch(0, "Dub")
    text, buttons, file = await message.read()
    assert text.startswith("Sure! I'll dub it in about")
    assert buttons is None
    assert file is None

    text, buttons, file = await message.read(timeout_sec=60)
    assert text.startswith("Here you are: https://")
    assert buttons is None
    assert file is None


@pytest.mark.asyncio
async def test_telegram_direct_upload_nonsense():
    # Test flow with unsupported mime_type
    message = Message("", SubMessage(""), mime_type="nonsense/mime")

    await telegram.dispatch(0, message)
    text, buttons, file = await message.read()
    assert (
        text
        == "Please send me a link to a YouTube video or Google Docs transcript or upload a video/audio here directly."  # noqa: E501
    )
    assert buttons is None
    assert file is None


@pytest.mark.asyncio
async def test_telegram_reset_after_error():
    # Test that you're able to resubmit a link after an error
    breaking = Message(
        "https://docs.google.com/document/d/1GUje5QOp_cPhQZ8NlGp4JdO0Vtc3ZmXfczahF1X9E9I/edit#",  # noqa: E501
    )

    await telegram.dispatch(0, breaking)
    text, buttons, file = await breaking.read()
    assert (
        text
        == "Would you like to translate, dub, or download the transcript as SRT or TXT?"
    )  # noqa: E501

    await telegram.dispatch(0, "SRT")
    text, buttons, file = await breaking.read()
    assert (
        text
        == "Invalid transcript format: SSMEXT. Supported values: ['SRT', 'SSMD', 'SSMD-NEXT']"
    )  # noqa: E501

    await telegram.dispatch(0, breaking)
    text, buttons, file = await breaking.read()
    assert (
        text
        == "Would you like to translate, dub, or download the transcript as SRT or TXT?"
    )  # noqa: E501
