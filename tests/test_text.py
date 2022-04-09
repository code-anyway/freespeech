from freespeech.lib import text


def test_chunk():
    assert text.chunk("Hello. World.", max_chars=7) == ["Hello.", "World."]
    assert text.chunk("Hello. World.", max_chars=13) == ["Hello. World."]
    assert text.chunk("Hello.", max_chars=6) == ["Hello."]
    assert text.chunk("Hello.", max_chars=1) == ['', 'Hello', '.']
