from freespeech.lib import speech, ssmd
from freespeech.types import Event, Voice


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
00:00:02 (Ada) There are five pre-conditions for peace.
00:00:03.00@1.00 (Greta) Hi!
00:00:04@2.00 (Grace) Hmm"""

    events = [
        Event(
            time_ms=0,
            chunks=["Hello #0.0# world!"],
            duration_ms=1000,
            voice=Voice(character="Alan", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=2000,
            chunks=["There are five pre-conditions for peace."],
            duration_ms=900,
            voice=Voice(character="Ada", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=3000,
            chunks=["Hi!"],
            duration_ms=900,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=4000,
            chunks=["Hmm"],
            duration_ms=None,
            voice=Voice(character="Grace", pitch=0.0, speech_rate=2.0),
        ),
    ]

    assert ssmd.parse(text) == events

    rendered_text = """00:00:00.00#1.00 (Alan) Hello #0.0# world!
00:00:02.00#0.90 (Ada) There are five pre-conditions for peace.
00:00:03.00#0.90 (Greta) Hi!
00:00:04.00@2.00 (Grace) Hmm"""
    assert ssmd.render(events) == rendered_text
