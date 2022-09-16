from freespeech.lib import text
from freespeech.types import Event, Voice

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
    assert text.chunk("Hello. World.", max_chars=13) == ["Hello. World."]
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


def test_chunk_overhead() -> None:
    # no overhead; text is split as is
    assert text.chunk("One. Two. Three", 10, sentence_overhead=0) == [
        "One. Two.",
        "Three",
    ]
    # adding some overhead to each sentence. Assuming we wrap each sentence in some
    # symbol, for example
    assert text.chunk("One. Two. Three", 10, sentence_overhead=2) == [
        "One.",
        "Two.",
        "Three",
    ]
    # now getting ready for SSML's <s> wrapping
    assert text.chunk("One. Two. Three", 14, sentence_overhead=len("<s></s>")) == [
        "One.",
        "Two.",
        "Three",
    ]


def test_chunk_raw() -> None:
    s = "abcdef"
    assert text.chunk_raw(s, 2) == ["ab", "cd", "ef"]
    assert text.chunk_raw(s, 3) == ["abc", "def"]
    assert text.chunk_raw(s, 4) == ["abcd", "ef"]
    assert text.chunk_raw(s, 1) == ["a", "b", "c", "d", "e", "f"]
    assert text.chunk_raw("", 1) == []


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


def test_break_phrases():
    expected = [
        Event(
            time_ms=1190,
            chunks=[
                "Queen Elizabeth the second had an unparalleled reign, the effect of which has been felt across the world."  # noqa: E501
            ],
            duration_ms=7000,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=9200,
            chunks=[
                "In her record-breaking 7 decades on the throne, she witnessed the end of the British Empire and welcomed radical societal shifts."  # noqa: E501
            ],
            duration_ms=8800,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=20230,
            chunks=[
                "She was the first person in the UK to make a long distance phone call without an operator, the first monarch in the world to send an e-mail, and one of the first to tweet."  # noqa: E501
            ],
            duration_ms=9790,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=30110,
            chunks=["The Queen's reign was monumental in absolutely every sense."],
            duration_ms=3270,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=33430,
            chunks=["It was peppered with superlatives."],
            duration_ms=2330,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=35830,
            chunks=["She was the longest reigning British monarch."],
            duration_ms=2450,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=38550,
            chunks=["Her head appeared on more coins than any other living monarch."],
            duration_ms=3470,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=42070,
            chunks=["She was herself like a monument, unchanging."],
            duration_ms=2930,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
    ]

    phrases = [
        (
            "Queen Elizabeth the second had an unparalleled reign, the effect of which has been felt across the world.",  # noqa: E501
            [
                ("queen", 1190.0, 370.0),
                ("elizabeth", 1570.0, 480.0),
                ("the", 2060.0, 120.0),
                ("second", 2190.0, 590.0),
                ("had", 2790.0, 170.0),
                ("an", 2970.0, 130.0),
                ("unparalleled", 3110.0, 890.0),
                ("reign", 4010.0, 710.0),
                ("the", 5110.0, 190.0),
                ("effect", 5310.0, 430.0),
                ("of", 5750.0, 110.0),
                ("which", 5870.0, 350.0),
                ("has", 6230.0, 140.0),
                ("been", 6380.0, 160.0),
                ("felt", 6550.0, 470.0),
                ("across", 7070.0, 530.0),
                ("the", 7610.0, 130.0),
                ("world", 7750.0, 440.0),
            ],
        ),
        (
            "In her record-breaking 7 decades on the throne, she witnessed the end of the British Empire and welcomed radical societal shifts.",  # noqa: E501
            [
                ("in", 9200.0, 240.0),
                ("her", 9450.0, 160.0),
                ("record", 9620.0, 350.0),
                ("breaking", 9980.0, 450.0),
                ("seven", 10440.0, 410.0),
                ("decades", 10860.0, 590.0),
                ("on", 11460.0, 130.0),
                ("the", 11600.0, 120.0),
                ("throne", 11730.0, 860.0),
                ("she", 12640.0, 330.0),
                ("witnessed", 12980.0, 430.0),
                ("the", 13420.0, 150.0),
                ("end", 13580.0, 290.0),
                ("of", 13880.0, 70.0),
                ("the", 13960.0, 100.0),
                ("british", 14070.0, 360.0),
                ("empire", 14440.0, 990.0),
                ("and", 15520.0, 250.0),
                ("welcomed", 15780.0, 490.0),
                ("radical", 16280.0, 590.0),
                ("societal", 16880.0, 610.0),
                ("shifts", 17500.0, 500.0),
            ],
        ),
        (
            "She was the first person in the UK to make a long distance phone call without an operator, the first monarch in the world to send an e-mail, and one of the first to tweet. The Queen's reign was monumental in absolutely every sense. It was peppered with superlatives. She was the longest reigning British monarch. Her head appeared on more coins than any other living monarch. She was herself like a monument, unchanging.",  # noqa: E501
            [
                ("she", 20230.0, 250.0),
                ("was", 20490.0, 130.0),
                ("the", 20630.0, 130.0),
                ("first", 20770.0, 290.0),
                ("person", 21070.0, 390.0),
                ("in", 21470.0, 80.0),
                ("the", 21560.0, 110.0),
                ("uk", 21680.0, 580.0),
                ("to", 22270.0, 130.0),
                ("make", 22410.0, 190.0),
                ("a", 22610.0, 50.0),
                ("long", 22670.0, 290.0),
                ("distance", 22970.0, 450.0),
                ("phone", 23430.0, 250.0),
                ("call", 23690.0, 240.0),
                ("without", 23940.0, 460.0),
                ("an", 24410.0, 130.0),
                ("operator", 24550.0, 890.0),
                ("the", 25590.0, 210.0),
                ("first", 25810.0, 290.0),
                ("monarch", 26110.0, 340.0),
                ("in", 26460.0, 100.0),
                ("the", 26570.0, 120.0),
                ("world", 26700.0, 400.0),
                ("to", 27110.0, 110.0),
                ("send", 27230.0, 230.0),
                ("an", 27470.0, 130.0),
                ("email", 27610.0, 610.0),
                ("and", 28270.0, 250.0),
                ("one", 28530.0, 210.0),
                ("of", 28750.0, 70.0),
                ("the", 28830.0, 130.0),
                ("first", 28970.0, 410.0),
                ("to", 29390.0, 110.0),
                ("tweet", 29510.0, 510.0),
                ("the", 30110.0, 230.0),
                ("queen's", 30350.0, 340.0),
                ("reign", 30700.0, 180.0),
                ("was", 30890.0, 120.0),
                ("monumental", 31020.0, 600.0),
                ("in", 31630.0, 150.0),
                ("absolutely", 31790.0, 690.0),
                ("every", 32490.0, 330.0),
                ("sense", 32830.0, 550.0),
                ("it", 33430.0, 210.0),
                ("was", 33650.0, 310.0),
                ("peppered", 33970.0, 470.0),
                ("with", 34450.0, 230.0),
                ("superlatives", 34690.0, 1070.0),
                ("she", 35830.0, 270.0),
                ("was", 36110.0, 150.0),
                ("the", 36270.0, 140.0),
                ("longest", 36420.0, 540.0),
                ("reigning", 36970.0, 470.0),
                ("british", 37450.0, 390.0),
                ("monarch", 37850.0, 430.0),
                ("her", 38290.0, 250.0),
                ("head", 38550.0, 210.0),
                ("appeared", 38770.0, 610.0),
                ("on", 39390.0, 210.0),
                ("more", 39610.0, 230.0),
                ("coins", 39850.0, 450.0),
                ("than", 40310.0, 210.0),
                ("any", 40530.0, 390.0),
                ("other", 40930.0, 330.0),
                ("living", 41270.0, 290.0),
                ("monarch", 41570.0, 450.0),
                ("she", 42070.0, 340.0),
                ("was", 42420.0, 540.0),
                ("herself", 43170.0, 670.0),
                ("like", 43850.0, 310.0),
                ("a", 44170.0, 30.0),
                ("monument", 44210.0, 790.0),
                ("unchanging", 45060.0, 920.0),
            ],
        ),
    ]

    assert text.break_speech(phrases=phrases, lang="en-US") == expected
