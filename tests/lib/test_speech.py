import json

import pytest

from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Event, Voice

AUDIO_EN_LOCAL = "tests/lib/data/media/en-US-mono.wav"
AUDIO_EN_GS = "gs://freespeech-tests/test_speech/en-US-mono.wav"

TEST_OUTPUT_GS = "gs://freespeech-tests/test_speech/output/"


def test_text_to_ssml_chunks():
    f = speech.text_to_ssml_chunks
    assert f("", 16, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill"><prosody rate="1.0"></prosody>'
        "</voice></speak>"
    ]
    assert f("Hello#1.0#world!", 100, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">'
        '<voice name="Bill"><prosody rate="1.0">Hello<break time="1.0s" />'
        "world!</prosody>"
        "</voice></speak>"
    ]
    assert f("Hello#1#world!", 100, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">'
        '<voice name="Bill">'
        '<prosody rate="1.0">Hello<break time="1s" />world!</prosody></voice></speak>'
    ]
    assert f("Hello#1#dear #2# world!", 100, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill">'
        '<prosody rate="1.0">'
        'Hello<break time="1s" />dear <break time="2s" /> world!'
        "</prosody></voice></speak>"
    ]
    # given the big XML overhead, this one fits into the 300-char limit of chunk...
    assert f("Hello#1#dear #2# world! How are you?", 300, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill">'
        '<prosody rate="1.0">'
        'Hello<break time="1s" />dear <break time="2s" /> world! How are you?'
        "</prosody></voice></speak>"  # noqa E501
    ]
    # but not into the 100-char limit
    assert f("Hello#1#dear #2# world! How are you?", 100, "Bill") == [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill">'
        '<prosody rate="1.0">'
        'Hello<break time="1s" />dear <break time="2s" /> world!</prosody>'
        "</voice></speak>",
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="Bill">'
        '<prosody rate="1.0">How are you?</prosody>'
        "</voice></speak>",
    ]


@pytest.mark.asyncio
async def test_transcribe() -> None:
    await obj.put(AUDIO_EN_LOCAL, AUDIO_EN_GS)
    (audio, *_), _ = media.probe(AUDIO_EN_LOCAL)
    assert not _

    t_en = await speech.transcribe(
        AUDIO_EN_GS, audio, "en-US", model="default", provider="Deepgram"
    )

    voice = Voice(character="Alan Turing", pitch=0.0, speech_rate=None)
    event = Event(
        time_ms=971, duration_ms=2006, chunks=["one, two three,"], voice=voice
    )
    assert t_en == [event]

    t_en = await speech.transcribe(AUDIO_EN_GS, audio, "en-US", model="default")

    event = Event(time_ms=0, duration_ms=3230, chunks=["1, 2 3."])
    assert t_en == [event]


@pytest.mark.asyncio
async def test_synthesize_text(tmp_path) -> None:
    output, voice = await speech.synthesize_text(
        text="One. Two. #2# Three.",
        duration_ms=4_000,
        voice="Grace Hopper",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
    )
    (audio, *_), _ = media.probe(output)

    eps = speech.SYNTHESIS_ERROR_MS
    assert abs(audio.duration_ms - 4_000) < eps
    # Although text is short, speech break helps us achieve reasonable speech rate
    assert voice.speech_rate == pytest.approx(0.78, 1e-2)
    assert voice.character == "Grace Hopper"
    assert voice.pitch == 0.0

    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")
    (first, second) = await speech.transcribe(
        output_gs, audio, "en-US", model="default"
    )

    assert first.chunks == ["One, two."]
    assert second.chunks == [" 3."]


@pytest.mark.asyncio
async def test_synthesize_azure_transcribe_google(tmp_path) -> None:
    output, voice = await speech.synthesize_text(
        text="Testing quite a long sentence. #2# Hello.",
        duration_ms=5_000,
        voice="Bill",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
    )
    (audio, *_), _ = media.probe(output)
    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")
    (first, second) = await speech.transcribe(
        output_gs, audio, "en-US", model="default"
    )

    assert first.chunks == ["Testing quite a long sentence."]
    assert second.chunks == [" Hello."]


@pytest.mark.asyncio
async def test_synthesize_events(tmp_path) -> None:
    events = [
        Event(time_ms=1_000, duration_ms=2_000, chunks=["One hen.", "Two ducks."]),
        Event(
            time_ms=5_000,
            duration_ms=2_000,
            chunks=["Three squawking geese."],
            voice=Voice("Grace Hopper"),
        ),
    ]

    output, voices = await speech.synthesize_events(
        events=events, voice="Alan Turing", lang="en-US", pitch=0.0, output_dir=tmp_path
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 7000) < eps

    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")

    t_en = await speech.transcribe(output_gs, audio, "en-US", model="default")

    assert t_en == [
        Event(time_ms=0, duration_ms=3270, chunks=["One hen two ducks."]),
        Event(time_ms=3270, duration_ms=3720, chunks=[" Three, squawking geese."]),
    ]

    voice_1, voice_2 = voices

    assert voice_1.speech_rate == 0.8625
    assert voice_1.character == "Alan Turing"
    assert voice_1.pitch == 0.0

    assert voice_2.speech_rate == 0.7655
    assert voice_2.character == "Grace Hopper"
    assert voice_2.pitch == 0.0

    events = [
        Event(
            time_ms=5_000,
            duration_ms=0,
            chunks=[""],
            voice=Voice("Grace Hopper"),
        ),
    ]

    output, voices = await speech.synthesize_events(
        events=events, voice="Alan Turing", lang="en-US", pitch=0.0, output_dir=tmp_path
    )
    (audio, *_), _ = media.probe(output)


@pytest.mark.asyncio
async def test_synthesize_long_event(tmp_path) -> None:
    event_en_us = Event(
        time_ms=205649,
        duration_ms=79029,
        chunks=[
            "in this Plan are implemented, Russia will lose the opportunity "
            "to finance the military machine. In particular, the Plan "
            "provides for restrictions on Russia's energy sector, banking "
            "sector, export-import operations, transport. The next steps "
            "should include an oil embargo and a complete restriction on "
            "oil supplies from Russia. We are also working to ensure that "
            "all – I emphasize – all Russian officials who support this "
            "shameful war receive a logical sanctions response from the "
            "democratic world. Russia must be recognized as a state-sponsor "
            "of terrorism, and the Russian Armed Forces must be recognized "
            "as a terrorist organization. The European Union is currently "
            "preparing a sixth package of sanctions. We discussed this "
            "today with Charles Michel. We are working to make it truly "
            "painful for the Russian military machine and the Russian state "
            "as a whole. I emphasize in all negotiations that sanctions are "
            "needed not as an end in themselves, but as a practical tool to "
            "motivate Russia to seek peace. It is important that the EU "
            "Delegation and the embassies of friendly countries resumed "
            "work in Kyiv."
        ],
        voice=None,
    )

    _, voices = await speech.synthesize_events(
        events=[event_en_us],
        voice="Alan Turing",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
    )

    (voice,) = voices

    assert voice.speech_rate == pytest.approx(0.762, rel=1e-3)


def test_normalize_speech() -> None:
    def test_pipeline(method: speech.Normalization):
        # Two events with 0ms in between, followed by another event in 1sec
        events = [
            Event(time_ms=100, duration_ms=300, chunks=["one"]),  # gap: 100ms
            Event(time_ms=500, duration_ms=400, chunks=["two."]),  # gap: 1200ms
            Event(time_ms=2_100, duration_ms=500, chunks=["three"]),
        ]

        normalized = speech.normalize_speech(
            events, gap_ms=2000, length=100, method=method
        )
        assert normalized == [
            Event(
                time_ms=100, duration_ms=2500, chunks=["one. #0.10# Two. #1.20# Three"]
            ),
        ]

        normalized = speech.normalize_speech(
            events, gap_ms=1000, length=100, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["one. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
        ]

        normalized = speech.normalize_speech(
            events, gap_ms=2000, length=5, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["one. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
        ]

        events += [
            Event(
                time_ms=2700,
                duration_ms=100,
                chunks=["four"],
                voice=Voice(character="Alonzo Church"),
            )
        ]
        events += [
            Event(
                time_ms=2900,
                duration_ms=100,
                chunks=["five"],
                voice=Voice(character="Alonzo Church"),
            )
        ]
        normalized = speech.normalize_speech(
            events, gap_ms=2000, length=5, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["one. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
            Event(
                time_ms=2700,
                duration_ms=300,
                chunks=["four. #0.10# Five"],
                voice=Voice(character="Alonzo Church"),
            ),
        ]

    test_pipeline("break_ends_sentence")
    test_pipeline("extract_breaks_from_sentence")


def test_normalize_speech_long() -> None:
    with open("tests/lib/data/youtube/transcript_ru_RU.json", encoding="utf-8") as fd:
        events_dict = json.load(fd)
        _ = [Event(**item) for item in events_dict]


def test_supported_azure_voices() -> None:
    voices = speech.supported_azure_voices()
    assert voices["uk-UA-PolinaNeural"] == "uk-UA"


@pytest.mark.asyncio
async def test_synthesize_azure(tmp_path) -> None:
    event_en_us = Event(
        time_ms=0,
        duration_ms=5000,
        chunks=["Hello this is Bill speaking #1# Nice to meet you."],
        voice=None,
    )

    _, voices = await speech.synthesize_events(
        events=[event_en_us],
        voice="Bill",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
    )

    (voice,) = voices

    assert voice.speech_rate == pytest.approx(0.87, rel=1e-2)
