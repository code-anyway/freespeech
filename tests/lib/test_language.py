import pytest

from freespeech.lib import language
from freespeech.lib.language import translate_deep_l
from freespeech.types import Event


@pytest.mark.asyncio
async def test_translate_text():
    text_ru = "Привет #2# мир. #3# Как дела?"
    text_en = "Hello #2# world. #3# How are you?"
    text_uk = "Привіт #2# світ. #3# Як справи?"

    assert await language.translate_google(text_en, "en-US", "ru-RU") == text_ru
    assert await language.translate_google(text_ru, "ru-RU", "uk-UK") == text_uk


@pytest.mark.asyncio
async def test_translate_events():
    events_ru = [
        Event(time_ms=0, duration_ms=1_000, chunks=["один", "", "два"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["три"]),
    ]
    events_en = [
        Event(time_ms=0, duration_ms=1_000, chunks=["one", "", "two"]),
        Event(time_ms=6_000, duration_ms=2_000, chunks=["three"]),
    ]

    assert await language.translate_events(events_ru, "ru-RU", "en-US") == events_en
    assert await language.translate_events(events_en, "en-US", "ru-RU") == events_ru


@pytest.mark.asyncio
async def test_translate_with_empty_chunks():
    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=["", "два"])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=["", "two"])]
    assert await language.translate_events(events_ru, "ru-RU", "en-US") == events_en

    events_ru = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    events_en = [Event(time_ms=0, duration_ms=1_000, chunks=[])]
    assert await language.translate_events(events_ru, "ru-RU", "en-US") == events_en


@pytest.mark.asyncio
async def test_translate_deep_l():
    source_text = "Привет. Я хочу быть переведенным с помощью DeepL. Сможем?"
    result = await translate_deep_l(source_text, "ru", "en")
    assert result == "Hi. I want to be translated using DeepL. Can we do that?"
