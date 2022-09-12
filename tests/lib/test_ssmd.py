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


def test_parse():
    text = """
00:00:00/00:00:05 (Alan) Hello #0.0# world!
00:00:01@1.0 (Greta) Hi!
@2.0 (Grace) Hmm"""

    expected = [
        Event(
            time_ms=0,
            chunks=["Hello #0.0# world!"],
            duration_ms=5000,
            voice=Voice(character="Alan", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=1000,
            chunks=["Hi!"],
            duration_ms=None,
            voice=Voice(character="Greta", pitch=0.0, speech_rate=1.0),
        ),
        Event(
            time_ms=None,
            chunks=["Hmm"],
            duration_ms=None,
            voice=Voice(character="Grace", pitch=0.0, speech_rate=2.0),
        ),
    ]

    assert ssmd.parse(text) == expected
