from freespeech.lib import text


def test_chunk():
    assert text.chunk("Hello. World.", max_chars=7) == ["Hello.", "World."]
    assert text.chunk("Hello. World.", max_chars=13) == ["Hello. World."]
    assert text.chunk("Hello.", max_chars=6) == ["Hello."]
    assert text.chunk("Hello.", max_chars=1) == ["", "Hello", "."]


def test_chunk_raw():
    s = "abcdef"
    assert text.chunk_raw(s, 2) == ["ab", "cd", "ef"]
    assert text.chunk_raw(s, 3) == ["abc", "def"]
    assert text.chunk_raw(s, 4) == ["abcd", "ef"]
    assert text.chunk_raw(s, 1) == ["a", "b", "c", "d", "e", "f"]
    assert text.chunk_raw("", 1) == []


def test_remove_symbols():
    s = "abcdef\n"
    assert text.remove_symbols(s, "\n") == "abcdef"
    assert text.remove_symbols(s, "abc\n") == "def"
    assert text.remove_symbols(s, "q") == "abcdef\n"
