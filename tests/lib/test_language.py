from freespeech.lib import language
from freespeech.types import Event


def test_translate_text():
    text_ru = "Привет, мир"
    text_en = "Hello world"
    text_uk = "Привіт світ"

    assert language.translate_text(text_en, "en-US", "ru-RU") == text_ru
    assert language.translate_text(text_ru, "ru-RU", "uk-UK") == text_uk


def test_translate_events():
    events_ru = [
        Event(time_ms=0, duration_ms=1_000, chunks=["один", "два"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["три"]),
    ]
    events_en = [
        Event(time_ms=0, duration_ms=1_000, chunks=["one", "two"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["three"]),
    ]

    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en
    assert language.translate_events(events_en, "en-US", "ru-RU") == events_ru


def test_translate_with_empty_chunks():
    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=["", "два"])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=["two"])]
    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en

    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en
