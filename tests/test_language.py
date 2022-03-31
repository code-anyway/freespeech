from freespeech.types import Transcript, Event

from freespeech import language


def test_translate():
    assert language.translate("Hello world", "en-US", "ru-RU") == "Привет мир"
    assert language.translate("Привет мир", "ru-RU", "uk-UK") == "Привіт світ"

    original = Transcript(
        lang="en-US",
        events=[
            Event(
                time_ms=0.0,
                duration_ms=1.5,
                chunks=["One hen", "Two ducks"]
            )
        ]
    )

    translation = language.translate(
        text=original, source=None, target="ru-RU")
    assert translation == Transcript(
        _id=translation._id,
        lang="ru-RU",
        events=[
            Event(
                time_ms=0.0,
                duration_ms=1.5,
                chunks=["Одна курица", "Две утки"]
            )
        ]
    )
