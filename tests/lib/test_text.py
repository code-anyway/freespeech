from freespeech.lib import text

TEXT = (
    "Думаю, саме там треба, щоб з’являлись журналісти, "
    "там, де людям це потрібно показувати #1.95# наших хлопців"
    " і дівчат героїчних людей. У нас складна ситуація "
    "на сході, #1.69# ситуація в Сєверодонецьку #1.70# Ви "
    "знаєте, ми тримаємо. #1.66# Саме тримаємо ситуацію. "
    "Їх більше вони потужніші, #1.14# але, тим не менш я"
    " думаю, в нас #1.58# є всі шанси боротися в цьому "
    "напрямку. Що стосується  Харкова, я думаю, ви знаєте там "
    "більше позитиву, там по трішечки крок за кроком, "
    "деокуповуються наші невеличкі села і громади. Що "
    "стосується Запоріжжя… #1.14# Я думаю, там найзагрозливіша "
    "ситуація. В запорізькій області. Через те що там "
    "частина окупована, а Запоріжжя постійно ворог як публічно,"
    " так і непублічно по перехватам, як ми розуміємо"
    " хоче окупувати #0.90# Запоріжжя. #3# І напевне, "
    "напевне, #1.18# в інших напрямках #1.62# ситуацію ми"
    " бачимо краще."
)

SENTENCES = [
    "Думаю, саме там треба, щоб з’являлись журналісти, "
    "там, де людям це потрібно показувати #1.95# наших хлопців "
    "і дівчат героїчних людей.",
    "У нас складна ситуація на сході, #1.69# ситуація в "
    "Сєверодонецьку #1.70# Ви знаєте, ми тримаємо. #1.66# "
    "Саме тримаємо ситуацію.",
    "Їх більше вони потужніші, #1.14# але, тим не менш я "
    "думаю, в нас #1.58# є всі шанси боротися в цьому "
    "напрямку.",
    "Що стосується  Харкова, я думаю, ви знаєте там більше "
    "позитиву, там по трішечки крок за кроком, "
    "деокуповуються наші невеличкі села і громади.",
    "Що стосується Запоріжжя… #1.14# Я думаю, там найзагрозливіша "
    "ситуація. В запорізькій області.",
    "Через те що там частина окупована, а Запоріжжя постійно "
    "ворог як публічно, так і непублічно по перехватам, "
    "як ми розуміємо хоче окупувати #0.90# Запоріжжя.",
    "#3# І напевне, напевне, #1.18# в інших напрямках #1.62# "
    "ситуацію ми бачимо краще.",
]


def test_chunk() -> None:
    assert text.chunk("", max_chars=10) == [""]
    assert text.chunk("Hello. World.", max_chars=7) == ["Hello.", "World."]
    assert text.chunk("Hello. World.", max_chars=14) == ["Hello. World."]
    assert text.chunk("Hello.", max_chars=6) == ["Hello."]
    assert text.chunk("Hello.", max_chars=1) == ["Hello."]
    assert text.chunk("Now. Two sentences, no dot at end", max_chars=1) == [
        "Now.",
        "Two sentences, no dot at end",
    ]

    # leading dot makes a sentence, but also get glued to the previous line if there
    # is enough max_chars. See next two tests; exactly 30 chars in text:
    assert text.chunk(". Leading dot makes a sentence", max_chars=29) == [
        ".",
        "Leading dot makes a sentence",
    ]
    assert text.chunk(". Leading dot makes a sentence", max_chars=30) == [
        ". Leading dot makes a sentence"
    ]

    assert text.chunk("Hello.", max_chars=1) == ["Hello."]
    assert text.chunk("Long sentence.", max_chars=5) == ["Long sentence."]


def test_chunk_raw() -> None:
    s = "abcdef"
    # check chunk by size behavior
    assert text.chunk_raw(s, 2) == ["ab", "cd", "ef"]
    assert text.chunk_raw(s, 3) == ["abc", "def"]
    assert text.chunk_raw(s, 4) == ["abcd", "ef"]
    assert text.chunk_raw(s, 1) == ["a", "b", "c", "d", "e", "f"]
    assert text.chunk_raw("", 1) == []

    # check chunk by punctuation (comma should not break sentence but '!' should
    assert text.chunk("One? Two. ", 1) == ["One?", "Two."]
    assert text.chunk("One. Two. ", 1) == ["One.", "Two."]
    assert text.chunk("One, Two. ", 1) == ["One, Two."]
    assert text.chunk("One. Two ", 1) == ["One.", "Two"]
    assert text.chunk("One! Two. ", 1) == ["One!", "Two."]



def test_remove_symbols() -> None:
    s = "abcdef\n"
    assert text.remove_symbols(s, "\n") == "abcdef"
    assert text.remove_symbols(s, "abc\n") == "def"
    assert text.remove_symbols(s, "q") == "abcdef\n"


def test_chunk_supports_dots_within_pauses() -> None:
    chunks = text.chunk(TEXT, 200)

    # ensure that there is even amount of hash signs
    for chunk in chunks:
        assert chunk.count("#") % 2 == 0

    # ensure the block breakdown is correct and we retain proper dots
    assert SENTENCES == chunks

    # ensure operation is not missing anything
    assert TEXT == " ".join(SENTENCES)

    # ensure the newlines are also fine
    chunks = text.chunk(
        "The newline is also a space char #2.1# after dot.\nThis is a second sentence",
        60,
    )
    assert chunks == [
        "The newline is also a space char #2.1# after dot.",
        "This is a second sentence",
    ]
