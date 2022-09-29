import pytest

from freespeech.lib import chat


@pytest.mark.asyncio
async def test_intent():
    intent, entities = await chat.intent(
        "load https://youtube.com/a and https://youTUBE.com/b using english and RuSSian subtitles and maCHINe a"  # noqa: E501
    )
    assert intent == "transcribe"
    assert entities == {
        "url": ["https://youtube.com/a", "https://youTUBE.com/b"],
        "language": ["en-US", "ru-RU"],
        "method": ["Subtitles", "Machine A"],
    }

    intent, entities = await chat.intent(
        "translate https://googledoc.COM/foo to engLISH"  # noqa: E501
    )
    assert intent == "translate"
    assert entities == {
        "url": ["https://googledoc.COM/foo"],
        "language": ["en-US"],
    }

    intent, entities = await chat.intent("dub https://googledoc.COM/foo")  # noqa: E501
    assert intent == "dub"
    assert entities == {
        "url": ["https://googledoc.COM/foo"],
    }

    intent, entities = await chat.intent(
        "transcribe https://youtube.com/a and https://youTUBE.com/b from EnGlISH"  # noqa: E501
    )
    assert intent == "transcribe"
    assert entities == {
        "url": ["https://youtube.com/a", "https://youTUBE.com/b"],
        "language": ["en-US"],
    }

    intent, entities = await chat.intent(
        "Transcribe https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing in English using SRT"  # noqa: E501
    )
    assert intent == "transcribe"
    assert entities == {
        "url": [
            "https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing"  # noqa: E501
        ],
        "language": ["en-US"],
        "method": ["srt"],
    }

    intent, entities = await chat.intent(
        "Load https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing in English using SRT"  # noqa: E501
    )
    assert intent == "transcribe"
    assert entities == {
        "url": [
            "https://docs.google.com/document/d/1E_E9S5G4vH6MWxo3qB4itXZRcSrFeqHscMysFjen-sY/edit?usp=sharing"  # noqa: E501
        ],
        "language": ["en-US"],
        "method": ["srt"],
    }


def test_generate_training_data():
    data = chat.generate_training_data(
        intents=["dub", "translate", "transcribe"], sample_sizes=[100, 100, 100]
    )

    # For some of the utterances there are duplicate samples and those are removed
    assert len(data) > 290
