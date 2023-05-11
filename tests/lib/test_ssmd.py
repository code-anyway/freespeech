from freespeech.lib import gdocs, speech, ssmd
from freespeech.types import Event, Transcript, Voice


def test_wrap_ssml():
    assert (
        speech._wrap_in_ssml("", voice="Bill", speech_rate=1.0)
        == '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill"><prosody rate="1.000000"></prosody>'
        "</voice></speak>"
    )
    # one sentence
    assert (
        speech._wrap_in_ssml("One.", voice="Bill", speech_rate=1.0)
        == '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill"><prosody rate="1.000000"><s>One.</s>'
        "</prosody></voice></speak>"
    )

    # two sentences
    assert (
        speech._wrap_in_ssml("One. Two.", voice="Bill", speech_rate=1.0)
        == '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill"><prosody rate="1.000000">'
        "<s>One. </s><s>Two.</s>"
        "</prosody></voice></speak>"
    )


def test_parse_and_render():
    text = """
00:00:00.00/00:00:01 (Alan) Hello #0.0# world!
00:00:02#1.00 (Ada) There are five pre-conditions for peace.

00:00:03.00#1.00 (Greta@1.2) Hi!
00:00:06 (Grace@2.00) Hmm"""

    events = [
        Event(
            group=0,
            time_ms=0,
            chunks=["Hello #0.0# world! #1.0#"],
            duration_ms=2000,
            voice=Voice(character="Alan", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            group=0,
            time_ms=2000,
            chunks=["There are five pre-conditions for peace."],
            duration_ms=1000,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            group=1,
            time_ms=3000,
            chunks=["Hi!"],
            duration_ms=1000,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.2),
        ),
        Event(
            chunks=[""],
            time_ms=4000,
            duration_ms=2000,
            group=1,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.2),
        ),
        Event(
            group=1,
            time_ms=6000,
            chunks=["Hmm"],
            duration_ms=None,
            voice=Voice(character="Grace", pitch=0.0, speech_rate=2.0),
        ),
    ]

    assert ssmd.parse(text) == events

    rendered_text = """00:00:00.00 (Alan) Hello #0.0# world! #1.0#
00:00:02.00#1.00 (Ada) There are five pre-conditions for peace.

00:00:03.00 (Greta@1.2) Hi!
00:00:04.00 (Greta@1.2)
00:00:06.00 (Grace@2.0) Hmm"""
    assert ssmd.render(events) == rendered_text
    assert ssmd.parse(rendered_text) == events

    url = gdocs.create(Transcript(events=events, lang="en-US"), "SSMD-NEXT")
    transcript = gdocs.load(url)
    assert transcript.events == events


def test_emojis_to_ssml_emotion_tags():
    text_in = "Hello world! 🤩 How are you?"
    text_out = (
        '<mstts:express-as style="excited">Hello world!</mstts:express-as>'
        '<mstts:express-as style="calm">How are you?</mstts:express-as>'
    )
    assert speech._emojis_to_ssml_emotion_tags(text_in, "en-US") == text_out

    text_in = (
        "Wrap every sentence of the input text containing an allowed emoji "
        "before the full stop into a 😌 corresponding "
        "ssml emotion tag 😢  . Ignore emojis in the middle or "
        "in the begining of the sentences🤩. Remove all "
        "the emojis from the input text😡. 😢😢."
    )
    text_out = (
        '<mstts:express-as style="calm">Wrap every sentence of the input text '
        "containing an allowed emoji before the full stop into a.</mstts:express-as>"
        '<mstts:express-as style="sad">corresponding ssml emotion tag.</mstts:express-as>'  # noqa: E501
        '<mstts:express-as style="excited">Ignore emojis in the middle or in '
        "the begining of the sentences.</mstts:express-as>"
        '<mstts:express-as style="angry">Remove all the emojis '
        "from the input text.</mstts:express-as>"
    )
    assert speech._emojis_to_ssml_emotion_tags(text_in, "en-US") == text_out


def test_collect_and_remove_emojis():
    text_in = (
        "Wrap every sentence of the input text containing an allowed emoji "
        "before the full stop into a 😌 corresponding "
        "ssml emotion tag 😢  . Ignore emojis in the middle or "
        "in the begining of the sentences🤩. Remove all "
        "the emojis from the input text😡. 😢😢."
    )
    text_out = (
        "Wrap every sentence of the input text containing an allowed emoji "
        "before the full stop into a corresponding "
        "ssml emotion tag. Ignore emojis in the middle or "
        "in the begining of the sentences. Remove all "
        "the emojis from the input text. ."
    )
    encountered_emojis = []
    assert speech._collect_and_remove_emojis(text_in, encountered_emojis) == text_out


def test_no_gaps_basic():
    events = [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=1000,
            chunks=["Goodbye!"],
            duration_ms=500,
        ),
        Event(
            time_ms=2000,
            chunks=["Hi!"],
            duration_ms=1500,
        ),
        Event(
            time_ms=3000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]

    aligned_events = ssmd.no_gaps(events, threshold_ms=1000)
    assert aligned_events == [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=1000,
            chunks=["Goodbye! #0.5#"],
            duration_ms=1000,
        ),
        Event(
            time_ms=2000,
            chunks=["Hi!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=3000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]

    assert (
        ssmd.render(aligned_events)
        == """00:00:00.00 (Ada) Hello!
00:00:01.00 (Ada) Goodbye! #0.5#
00:00:02.00 (Ada) Hi!
00:00:03.00#1.00 (Ada) Bye!"""
    )


def test_no_gaps_with_long_pauses():
    events = [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=2500,
            chunks=["Goodbye!"],
            duration_ms=500,
        ),
        Event(
            time_ms=3000,
            chunks=["Hi!"],
            duration_ms=1500,
        ),
        Event(
            time_ms=5000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]

    aligned_events = ssmd.no_gaps(events, threshold_ms=1000)
    assert aligned_events == [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=1000,
            chunks=[""],
            duration_ms=1500,
        ),
        Event(
            time_ms=2500,
            chunks=["Goodbye!"],
            duration_ms=500,
        ),
        Event(
            time_ms=3000,
            chunks=["Hi! #0.5#"],
            duration_ms=2000,
        ),
        Event(
            time_ms=5000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]

    assert (
        ssmd.render(aligned_events)
        == """00:00:00.00 (Ada) Hello!
00:00:01.00 (Ada)
00:00:02.50 (Ada) Goodbye!
00:00:03.00 (Ada) Hi! #0.5#
00:00:05.00#1.00 (Ada) Bye!"""
    )


def test_render_comments():
    events = [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
            comment="Comment 1",
        ),
        Event(
            time_ms=1000,
            chunks=["Goodbye!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=2000,
            chunks=["Hi!"],
            duration_ms=1000,
            comment="Comment 2",
        ),
        Event(
            time_ms=3000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]

    assert (
        ssmd.render(events)
        == """00:00:00.00 (Ada) Hello!
[Comment 1]
00:00:01.00 (Ada) Goodbye!
00:00:02.00 (Ada) Hi!
[Comment 2]
00:00:03.00#1.00 (Ada) Bye!"""
    )

    # We are not expecting to restore comments from the rendered text
    assert ssmd.parse(ssmd.render(events)) == [
        Event(
            time_ms=0,
            chunks=["Hello!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=1000,
            chunks=["Goodbye!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=2000,
            chunks=["Hi!"],
            duration_ms=1000,
        ),
        Event(
            time_ms=3000,
            chunks=["Bye!"],
            duration_ms=1000,
        ),
    ]


def test_render_block_newlines():
    events = [
        Event(
            time_ms=0,
            chunks=["Hello\nWorld."],
            duration_ms=1000,
            group=0,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            comment=None,
        )
    ]
    assert ssmd.render_block(events) == "00:00:00.00#1.00 (Ada) Hello World."


def test_parse_body():
    ssmd_examples = [
        # Example
        (
            """
What is the meaning of life?""",
            [
                {
                    "time": None,
                    "speaker": None,
                    "text": "What is the meaning of life?",
                    "fixed": False,
                }
            ],
        ),
        # Example
        (
            """

What is the meaning of life?""",
            [
                {
                    "time": None,
                    "speaker": None,
                    "text": "What is the meaning of life?",
                    "fixed": False,
                }
            ],
        ),
        # Example
        ("""""", []),
        # Example
        (
            """(Bill) Hello world! How are you?
(Sam) I'm good, how are you?""",
            [
                {
                    "time": None,
                    "speaker": "Bill",
                    "text": "Hello world! How are you?",
                    "fixed": False,
                },
                {
                    "time": None,
                    "speaker": "Sam",
                    "text": "I'm good, how are you?",
                    "fixed": False,
                },
            ],
        ),
        # Example
        (
            """(Bill) Hello world!
How are you?
(Sam) I'm good, how are you?""",
            [
                {
                    "time": None,
                    "speaker": "Bill",
                    "text": "Hello world! How are you?",
                    "fixed": False,
                },
                {
                    "time": None,
                    "speaker": "Sam",
                    "text": "I'm good, how are you?",
                    "fixed": False,
                },
            ],
        ),
        # Example
        (
            """

00:00 (Bill) Hello world!

00:02 How are you?
(Sam) I'm good, how are you?""",
            [
                {
                    "time": "00:00",
                    "speaker": "Bill",
                    "text": "Hello world!",
                    "fixed": True,
                },
                {
                    "time": "00:02",
                    "speaker": None,
                    "text": "How are you?",
                    "fixed": True,
                },
                {
                    "time": None,
                    "speaker": "Sam",
                    "text": "I'm good, how are you?",
                    "fixed": False,
                },
            ],
        ),
        # Example
        (
            """

00:00 (Bill) Hello world!
00:01 How are you?

00:00:02.005 (Sam) I'm good, how are you?
You look great!""",
            [
                {
                    "time": "00:00",
                    "speaker": "Bill",
                    "text": "Hello world!",
                    "fixed": True,
                },
                {
                    "time": "00:01",
                    "speaker": None,
                    "text": "How are you?",
                    "fixed": False,
                },
                {
                    "time": "00:00:02.005",
                    "speaker": "Sam",
                    "text": "I'm good, how are you? You look great!",
                    "fixed": True,
                },
            ],
        ),
        # Example
        (
            """
00:00 (Bill) Hello world!

00:00:01.40 How are you?""",
            [
                {
                    "time": "00:00",
                    "speaker": "Bill",
                    "text": "Hello world!",
                    "fixed": True,
                },
                {
                    "time": "00:00:01.40",
                    "speaker": None,
                    "text": "How are you?",
                    "fixed": True,
                },
            ],
        ),
        # Example
        (
            """00:00 (Bill) Hello world!
[This is a comment]
00:00:01.40 How are you?""",
            [
                {
                    "time": "00:00",
                    "speaker": "Bill",
                    "text": "Hello world!",
                    "comment": "This is a comment",
                    "fixed": True,
                },
                {
                    "time": "00:00:01.40",
                    "speaker": None,
                    "text": "How are you?",
                    "fixed": False,
                },
            ],
        ),
        # Example
        (
            """
00:00 (Bill) Hello world!
[This is a multi-line

comment]
00:00:01.40 How are you?""",
            [
                {
                    "time": "00:00",
                    "speaker": "Bill",
                    "text": "Hello world!",
                    "comment": "This is a multi-line\n\ncomment",
                    "fixed": True,
                },
                {
                    "time": "00:00:01.40",
                    "speaker": None,
                    "text": "How are you?",
                    "fixed": False,
                },
            ],
        ),
    ]
    for text, value in ssmd_examples:
        assert ssmd.parse_body(text) == value, text


def test_make_events():
    # Example
    assert ssmd.make_events(
        [
            {
                "time": None,
                "speaker": None,
                "text": "What is the meaning of life?",
                "fixed": False,
            }
        ]
    ) == [
        Event(time_ms=None, chunks=["What is the meaning of life?"], duration_ms=None)
    ]
