import asyncio

import pytest

from freespeech import telegram


class Message(object):
    def __init__(self, text, messages):
        self.raw_text = text
        self.replies = messages
        self.sender_id = 0
        self.sender = None

    async def reply(self, message, buttons, force_document, link_preview, file=None):
        self.replies.append((message, buttons, file))
        return self


class TelegramClient(object):
    def __init__(self, messages):
        self.messages = messages

    async def send_message(self, *args, **kwargs):
        message = Message(*args, **kwargs)
        self.messages.append(message)
        return message


async def read(messages):
    while not messages:
        await asyncio.sleep(0.1)
    return messages.pop()


@pytest.mark.asyncio
async def test_telegram():
    messages = []
    client = TelegramClient(messages)
    message = Message("https://www.youtube.com/watch?v=306gVIj3LsM", messages)

    await telegram.dispatch(client, 0, message)
    text, buttons, file = await read(messages)
    assert text == "Create transcript using Subtitles or Speech Recognition?"
    assert [button.text for button in buttons] == ["Subtitles", "Speech Recognition"]
    assert file is None

    await telegram.dispatch(client, 0, "Subtitles")
    text, buttons, file = await read(messages)
    assert text == "Please select or send the language."
    assert [button.text for button in buttons] == ["EN", "UA", "ES", "FR", "DE", "PT"]
    assert file is None

    await telegram.dispatch(client, 0, "EN")
    text, buttons, file = await read(messages)
    assert (
        text == "Sure! Give me 35 seconds to transcribe it in en-US using Subtitles."
    )  # noqa E501
    assert buttons is None
    assert file is None

    text, buttons, file = await read(messages)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None

    async def initiate(url):
        message = Message(url, messages)
        await telegram.dispatch(client, 0, message)
        text, buttons, file = await read(messages)
        assert (
            text
            == "Would you like to translate, dub, or download the transcript as SRT or TXT?"  # noqa E501
        )  # noqa E501
        assert [button.text for button in buttons] == ["Translate", "Dub", "SRT", "TXT"]
        assert file is None
        return message

    url = text[len("Here you are: ") :]
    message = await initiate(url)
    await telegram.dispatch(client, 0, "SRT")
    text, buttons, file = await read(messages)
    assert text == "SRT"
    assert buttons is None
    with open(file, "rb") as f:
        data = f.read()
        assert data.decode("utf-8").startswith(
            "1\n00:00:00,060 --> 00:04:02,320\nfive sound four it's really quite remarkable you probably expected the Roar and Rumble of this rocket launch"  # noqa E501
        )  # noqa E501

    message = await initiate(url)
    await telegram.dispatch(client, 0, "TXT")
    text, buttons, file = await read(messages)
    assert text == "Plain text"
    assert buttons is None
    with open(file, "rb") as f:
        data = f.read()
        assert data.decode("utf-8").startswith(
            "five sound four it's really quite remarkable you probably expected the Roar and Rumble of this rocket launch"  # noqa E501
        )  # noqa E501

    message = await initiate(url)
    await telegram.dispatch(client, 0, "Translate")
    text, buttons, file = await read(messages)
    assert text == "Please select or send the language."
    assert [button.text for button in buttons] == ["EN", "UA", "ES", "FR", "DE", "PT"]
    assert file is None

    await telegram.dispatch(client, 0, "Russian")  # try full language name
    text, buttons, file = await read(messages)
    assert text == "Sure! I'll translate it in about 11 seconds."
    assert buttons is None
    assert file is None

    text, buttons, file = await read(messages)
    assert text.startswith("Here you are: https://docs.google.com/document/d/")
    assert buttons is None
    assert file is None

    url = text[len("Here you are: ") :]
    message = await initiate(url)
    await telegram.dispatch(client, 0, "Dub")
    text, buttons, file = await read(messages)
    assert text.startswith("Sure! I'll dub it in about")
    assert buttons is None
    assert file is None

    text, buttons, file = await read(messages)
    assert text.startswith("Here you are: https://")
    assert buttons is None
    assert file is None
