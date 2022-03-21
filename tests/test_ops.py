import freespeech.ops as ops


PROJECT_ID = "freespeech-343914"


def test_google_docs():
    res = ops.extract_text_from_google_docs("https://docs.google.com/document/d/1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit")
    assert res == "Hello World\n\nNew Paragraph\n"


def test_translate_text():
    assert ops.translate_text("Hello world", "en-US", "ru-RU", PROJECT_ID) == "Привет мир"
    assert ops.translate_text("Привет мир", "ru-RU", "uk-UK", PROJECT_ID) == "Привіт світ"