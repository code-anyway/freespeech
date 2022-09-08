from freespeech.lib import language
from freespeech.lib.language import deep_l_supported, translate_deep_l
from freespeech.types import Event


def test_translate_text():
    text_ru = "Привет #2# мир. #3# Как дела?"
    text_en = "Hello #2# world. #3# How are you?"
    text_uk = "Привіт #2# світ. #3# Як справи?"

    assert language.translate_google(text_en, "en-US", "ru-RU") == text_ru
    assert language.translate_google(text_ru, "ru-RU", "uk-UK") == text_uk


def test_translate_events():
    events_ru = [
        Event(time_ms=0, duration_ms=1_000, chunks=["один", "", "два"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["три"]),
    ]
    events_en = [
        Event(time_ms=0, duration_ms=1_000, chunks=["one", "", "two"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["three"]),
    ]

    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en
    assert language.translate_events(events_en, "en-US", "ru-RU") == events_ru


def test_translate_with_empty_chunks():
    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=["", "два"])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=["", "two"])]
    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en

    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    assert language.translate_events(events_ru, "ru-RU", "en-US") == events_en


def test_translate_deep_l():
    source_text = "Привет. Я хочу быть переведенным с помощью DeepL. Сможем?"
    result = translate_deep_l(source_text, "ru-RU", "en-GB")
    assert result == "Hi. I want to be translated using DeepL. Can we do that?"


def test_translate_deep_l_pauses():
    source_text = (
        "Привет #1.0#. Я хочу #0.23# быть переведенным с #0# помощью DeepL. #1# Сможем?"
    )
    result = translate_deep_l(source_text, "ru-RU", "en-GB")
    assert (
        result == "Hi #1.0#. I want #0.23# to be translated from #0# using "
        "DeepL. #1# Can we do that?"
    )


def test_language_pairs():
    assert deep_l_supported("en-US", "en-GB")
    assert deep_l_supported("ru-RU", "en-GB")
    assert deep_l_supported("uk-UK", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "en")
