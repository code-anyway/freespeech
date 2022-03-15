import freespeech.ops as ops


def test_google_docs():
    res = ops.extract_text_from_google_docs("https://docs.google.com/document/d/1OlGGnR41Z7rC3UKxgiMSSlfvvfa_vddw3JHaKbP8z6w/edit")
    assert res == "Hello World\n\nNew Paragraph\n"
