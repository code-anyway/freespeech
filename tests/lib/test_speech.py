import json
from typing import Sequence, get_args

import pytest

from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Character, Event, Language, Voice, assert_never

AUDIO_EN_LOCAL = "tests/lib/data/media/en-US-mono.wav"
AUDIO_EN_GS = "gs://freespeech-tests/test_speech/en-US-mono.wav"

TEST_OUTPUT_GS = "gs://freespeech-tests/test_speech/output/"


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


def test_text_to_chunks():
    f = speech.text_to_chunks
    assert f("", 16, "Bill") == [""]
    assert f("Hello#1.0#world!", 100, "Bill") == ['Hello<break time="1.0s" />world!']
    assert f("Hello#1#dear #2# world!", 100, "Bill") == [
        'Hello<break time="1s" />dear <break time="2s" /> world!'
    ]
    # given the big XML overhead, this one fits into the 300-char limit of chunk...
    assert f("Hello #1# dear #2# world! How are you?", 300, "Bill") == [
        'Hello <break time="1s" /> dear <break time="2s" /> world! How are you?'
    ]
    # but not into the 100-char limit
    assert f("Hello #1# dear #2# world! How are you?", 100, "Bill") == [
        'Hello <break time="1s" /> dear <break time="2s" /> world!',
        "How are you?",
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
    assert voice.speech_rate == pytest.approx(0.8551, 1e-2)
    assert voice.character == "Grace Hopper"
    assert voice.pitch == 0.0

    output_gs = await obj.put(output, f"{TEST_OUTPUT_GS}{output.name}")
    (first, second) = await speech.transcribe(
        output_gs, audio, "en-US", model="default"
    )

    assert first.chunks == ["One, two."]
    assert second.chunks == [" 3."]

    output, voice = await speech.synthesize_text(
        text="One. Two. #2# Three.",
        duration_ms=None,
        voice="Grace Hopper",
        lang="en-US",
        pitch=0.0,
        output_dir=tmp_path,
        init_rate=3.0,
    )


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
    # test_pipeline("extract_breaks_from_sentence")


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


def test_voices_and_languages_completeness() -> None:
    """
    Ensure that we have a voice for each character/language combination. Otherwise
    this might lead to some errors
    Returns:
    """
    supported_languages: Sequence[Language] = get_args(Language)
    all_characters: Sequence[Character] = get_args(Character)

    # 1 check that all characters have their voice definitions
    # this is the completeness check, the other end is ensured by the type checking (we
    # can not use wrong literal for character)
    for character in all_characters:
        assert character in speech.VOICES.keys()

    # 2 check that whenever we have a character defined, they support all languages
    for character, voices in speech.VOICES.items():
        for lang in supported_languages:
            assert voices.get(
                lang, None
            ), f"Language {lang} not found for character {character}"

    # 3 check that real voices are supported by the provider (no typo) and we support
    # all the providers
    for character, supported_voices in speech.VOICES.items():
        for language, voice in supported_voices.items():
            provider, provider_voice = voice
            match provider:
                case "Google":
                    assert language in speech.supported_google_voices()[provider_voice]
                case "Azure":
                    assert language in speech.supported_azure_voices()[provider_voice]
                case "Deepgram":
                    raise ValueError("Deepgram can not be a ")
                case never:
                    assert_never(never)
