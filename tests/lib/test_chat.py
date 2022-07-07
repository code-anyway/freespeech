import pytest

from freespeech.lib import chat


@pytest.mark.asyncio
async def test_intent():
    intent, entities = await chat.intent(
        "load https://youtube.com/a and https://youtube.com/b using English and Russian subtitles"  # noqa: E501
    )
    intent == "load"
    assert entities == {
        "url": ["https://youtube.com/a", "https://youtube.com/b"],
        "language": ["en-US", "ru-RU"],
        "method": ["subtitles"],
    }


def test_training_data():
    data = chat.training_data(
        intents=["dub", "translate", "transcribe"], sample_sizes=[100, 100, 100]
    )
    assert len(data) == 300
