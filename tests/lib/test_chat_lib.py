import pytest

from freespeech.lib import chat


@pytest.mark.asyncio
async def test_intent():
    intent, entities = await chat.intent(
        "load https://youtube.com/a and https://youTUBE.com/b using english and RuSSian subtitles and maCHINe a"  # noqa: E501
    )
    intent == "load"
    assert entities == {
        "url": ["https://youtube.com/a", "https://youTUBE.com/b"],
        "language": ["en-US", "ru-RU"],
        "method": ["Subtitles", "Machine A"],
    }

    intent, entities = await chat.intent(
        "translate https://googledoc.COM/foo to engLISH"  # noqa: E501
    )
    intent == "translate"
    assert entities == {
        "url": ["https://googledoc.COM/foo"],
        "language": ["en-US"],
    }

    intent, entities = await chat.intent("dub https://googledoc.COM/foo")  # noqa: E501
    intent == "dub"
    assert entities == {
        "url": ["https://googledoc.COM/foo"],
    }


def test_generate_training_data():
    data = chat.generate_training_data(
        intents=["dub", "translate", "transcribe"], sample_sizes=[100, 100, 100]
    )

    # For some of the utterances there are duplicate samples and those are removed
    assert len(data) > 290
