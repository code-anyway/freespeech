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
    assert (
        result == "Hi. I want to be translated with the help of DeepL. Can we do that?"
    )


def test_translate_deep_l_pauses():
    source_text = (
        "Привет #1.0#. Я хочу #0.23# быть переведенным с #0# помощью DeepL. #1# Сможем?"
    )
    result = translate_deep_l(source_text, "ru-RU", "en-GB")
    assert (
        result == "Hi #1.0#. I want #0.23# to be translated from #0# using "
        "DeepL. #1# Can we do that?"
    )


def test_translate_with_speech_pause_numbers():
    source_text = (
        "Queen Elizabeth the second had an unparalleled reign, "
        "the effect of which has been felt across the world. #0.98# "
        "In her record-breaking seven decades on the throne, she witnessed "
        "the end of the British empire and welcomed radical societal shifts."
    )
    result = translate_deep_l(source_text, "en-GB", "ru-RU")
    assert (
        result == "Королева Елизавета Вторая пережила беспрецедентное правление, "
        "последствия которого ощущаются во всем мире. #0.98# За рекордные "
        "семь десятилетий своего пребывания на троне она стала свидетелем"
        " конца Британской империи и приветствовала радикальные "
        "изменения в обществе."
    )


def test_language_pairs():
    assert deep_l_supported("en-US", "en-GB")
    assert deep_l_supported("ru-RU", "en-GB")
    assert deep_l_supported("uk-UK", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "ru-RU")
    assert not deep_l_supported("ko-KR", "en")
