import json
import tempfile
from typing import Sequence, get_args

import pytest

from freespeech import env
from freespeech.lib import media, speech
from freespeech.lib.storage import obj
from freespeech.types import Character, Event, Language, Voice, assert_never

AUDIO_EN_LOCAL = "tests/lib/data/media/en-US-mono.wav"
AUDIO_EN_GS = "gs://freespeech-tests/test_speech/en-US-mono.wav"

TEST_OUTPUT_GS = "gs://freespeech-tests/test_speech/output/"

# Tolerance in milliseconds for event time and duration
# Our tests are relying on synthesizing/transcribing and
# numbers do fluctuate depending on models and other hyper-parameters.
ABSOLUTE_ERROR_MS = 50


def test_text_to_chunks():
    f = speech.text_to_chunks
    assert f("", 16, "Bill", 1.0) == [""]
    assert f("Hello#1.0#world!", 100, "Bill", 1.0) == [
        'Hello<break time="1.0s" />world!'
    ]
    assert f("Hello#1#dear #2# world!", 100, "Bill", 1.0) == [
        'Hello<break time="1s" />dear <break time="2s" /> world!'
    ]
    # given the big XML overhead, this one fits into the 300-char limit of chunk...
    assert f("Hello #1# dear #2# world! How are you?", 300, "Bill", 1.0) == [
        'Hello <break time="1s" /> dear <break time="2s" /> world! How are you?'
    ]
    # but not into the 100-char limit
    assert f("Hello #1# dear #2# world! How are you?", 100, "Bill", 1.0) == [
        'Hello <break time="1s" /> dear <break time="2s" /> world!',
        "How are you?",
    ]


@pytest.mark.asyncio
async def test_transcribe(tmp_path) -> None:
    downmixed_local = await media.multi_channel_audio_to_mono(
        file=AUDIO_EN_LOCAL, output_dir=tmp_path
    )
    await obj.put(downmixed_local, AUDIO_EN_GS)

    t_en = await speech.transcribe(AUDIO_EN_GS, "en-US", provider="Deepgram", model="default")

    voice = Voice(character="Alan", pitch=0.0, speech_rate=1.0)
    event = Event(
        time_ms=971, duration_ms=2006, chunks=["one, two three,"], voice=voice
    )
    assert t_en == [event]

    t_en = await speech.transcribe(AUDIO_EN_GS, "en-US", provider="Google", model="latest_long")

    assert event.time_ms == 971
    assert event.duration_ms == pytest.approx(2006, abs=ABSOLUTE_ERROR_MS)
    assert event.chunks == ["one, two three,"]


@pytest.mark.asyncio
async def test_synthesize_text(tmp_path) -> None:
    output, voice = await speech.synthesize_text(
        text="One. Two. #2# Three.",
        duration_ms=4_000,
        voice=Voice(character="Grace"),
        lang="en-US",
        output_dir=tmp_path,
    )
    (audio, *_), _ = media.probe(output)

    eps = speech.SYNTHESIS_ERROR_MS
    assert abs(audio.duration_ms - 4_000) < eps
    # Although text is short, speech break helps us achieve reasonable speech rate
    assert voice.speech_rate == pytest.approx(0.8551, 1e-2)
    assert voice.character == "Grace"
    assert voice.pitch == 0.0

    downmixed_local = await media.multi_channel_audio_to_mono(
        output, output_dir=tmp_path
    )
    output_gs = await obj.put(downmixed_local, f"{TEST_OUTPUT_GS}{output.name}")

    (first, second) = await speech.transcribe(output_gs, "en-US", provider="Google", model="latest_long")
    print(obj.public_url(output_gs))
    assert first.chunks == ["1 2"]
    assert second.chunks == [" 3"]

    fast_output, voice = await speech.synthesize_text(
        text="One. Two. #2# Three.",
        duration_ms=None,
        voice=Voice(character="Grace", speech_rate=20),
        lang="en-US",
        output_dir=tmp_path,
    )
    assert voice.speech_rate == 20  # making sure that this ignores maximum
    slow_output, voice = await speech.synthesize_text(
        text="One. Two. #2# Three.",
        duration_ms=None,
        voice=Voice(character="Grace", speech_rate=0.3),
        lang="en-US",
        output_dir=tmp_path,
    )

    (fast_audio, *_), _ = media.probe(fast_output)
    (slow_audio, *_), _ = media.probe(slow_output)
    assert voice.speech_rate == 0.3  # making sure that this ignores minimum
    assert slow_audio.duration_ms > fast_audio.duration_ms  # slow is slower than fast 🧠


@pytest.mark.asyncio
async def test_synthesize_azure_transcribe_google(tmp_path) -> None:
    output, voice = await speech.synthesize_text(
        text="Testing quite a long sentence. #2# Hello.",
        duration_ms=5_000,
        voice=Voice(character="Bill"),
        lang="en-US",
        output_dir=tmp_path,
    )

    downmixed_local = await media.multi_channel_audio_to_mono(
        output, output_dir=tmp_path
    )
    output_gs = await obj.put(downmixed_local, f"{TEST_OUTPUT_GS}{output.name}")

    (first, second) = await speech.transcribe(output_gs, "en-US", provider="Google", model="latest_long")
    assert first.chunks == ["Testing quite a long sentence."]
    assert second.chunks == [" Hello."]


@pytest.mark.asyncio
async def test_synthesize_google_transcribe_azure(tmp_path) -> None:
    output, _ = await speech.synthesize_text(
        text="Testing quite a long sentence. #2# Hello.",
        duration_ms=5_000,
        voice=Voice(character="Alonzo"),
        lang="en-US",
        output_dir=tmp_path,
    )

    downmixed_local = await media.multi_channel_audio_to_mono(
        output, output_dir=tmp_path
    )
    output_gs = await obj.put(downmixed_local, f"{TEST_OUTPUT_GS}{output.name}")

    (first, second) = await speech.transcribe(output_gs, lang="en-US", provider="Azure", model="default")
    assert first.chunks == ["Testing quite a long sentence."]
    assert second.chunks == ["Hello."]


@pytest.mark.asyncio
async def test_synthesize_google_transcribe_azure_granular(tmp_path) -> None:
    output, _ = await speech.synthesize_text(
        text="Testing quite a long sentence. Hello.",
        duration_ms=3_000,
        voice=Voice(character="Alonzo"),
        lang="en-US",
        output_dir=tmp_path,
    )

    downmixed_local = await media.multi_channel_audio_to_mono(
        output, output_dir=tmp_path
    )
    output_gs = await obj.put(downmixed_local, f"{TEST_OUTPUT_GS}{output.name}")

    # With no "model" provided Azure transcription will not break sentences.
    (first, *_) = await speech.transcribe(output_gs, lang="en-US", provider="Azure", model="default")
    assert first.chunks == ["Testing quite a long sentence. Hello."]

    # mode="azure_granular" will create one event per sentence.
    (first, second) = await speech.transcribe(
        output_gs, lang="en-US", provider="Azure", model="azure_granular"
    )
    assert first.chunks == ["Testing quite a long sentence."]
    assert second.chunks == ["Hello."]


@pytest.mark.asyncio
async def test_synthesize_events(tmp_path) -> None:
    events = [
        Event(
            time_ms=1_000,
            duration_ms=2_000,
            chunks=["One hen.", "Two ducks."],
            voice=Voice(character="Alan"),
        ),
        Event(
            time_ms=5_000,
            duration_ms=2_000,
            chunks=["Three squawking geese."],
            voice=Voice(character="Grace"),
        ),
    ]

    output, voices, spans = await speech.synthesize_events(
        events=events, lang="en-US", output_dir=tmp_path
    )
    (audio, *_), _ = media.probe(output)

    eps = 100
    assert abs(audio.duration_ms - 7000) < eps
    # is this deterministic?
    assert spans == [
        ("blank", 0, 1000),
        ("event", 1000, 2975),
        ("blank", 2975, 5000),
        ("event", 5000, 7027),
    ]

    downmixed_local = await media.multi_channel_audio_to_mono(
        output, output_dir=tmp_path
    )
    output_gs = await obj.put(downmixed_local, f"{TEST_OUTPUT_GS}{output.name}")

    t_en = await speech.transcribe(output_gs, "en-US", provider="Google", model="latest_long")

    first, second = t_en

    assert first.time_ms == 0
    assert first.duration_ms == pytest.approx(3270, abs=ABSOLUTE_ERROR_MS)
    assert first.chunks == ["One, hen two ducks."]

    assert second.time_ms == pytest.approx(3270, abs=ABSOLUTE_ERROR_MS)
    assert second.duration_ms == pytest.approx(3720, abs=ABSOLUTE_ERROR_MS)
    assert second.chunks == [" three squawking geese"]

    voice_1, voice_2 = voices

    assert voice_1.speech_rate == 0.8625
    assert voice_1.character == "Alan"
    assert voice_1.pitch == 0.0

    assert voice_2.speech_rate == 0.7655
    assert voice_2.character == "Grace"
    assert voice_2.pitch == 0.0

    events = [
        Event(
            time_ms=5_000,
            duration_ms=0,
            chunks=[""],
            voice=Voice(character="Grace"),
        ),
    ]

    output, voices, spans = await speech.synthesize_events(
        events=events, lang="en-US", output_dir=tmp_path
    )
    assert spans == [("blank", 0, 5000), ("event", 5000, 5000)]
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
        voice=Voice(character="Alan"),
    )

    _, voices, _ = await speech.synthesize_events(
        events=[event_en_us],
        lang="en-US",
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
                time_ms=100, duration_ms=2500, chunks=["One. #0.10# Two. #1.20# Three"]
            ),
        ]

        normalized = speech.normalize_speech(
            events, gap_ms=1000, length=100, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["One. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
        ]

        normalized = speech.normalize_speech(
            events, gap_ms=2000, length=5, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["One. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
        ]

        events += [
            Event(
                time_ms=2700,
                duration_ms=100,
                chunks=["four"],
                voice=Voice(character="Alonzo"),
            )
        ]
        events += [
            Event(
                time_ms=2900,
                duration_ms=100,
                chunks=["five"],
                voice=Voice(character="Alonzo"),
            )
        ]
        normalized = speech.normalize_speech(
            events, gap_ms=2000, length=5, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["One. #0.10# Two."]),
            Event(time_ms=2100, duration_ms=500, chunks=["three"]),
            Event(
                time_ms=2700,
                duration_ms=300,
                chunks=["Four. #0.10# Five"],
                voice=Voice(character="Alonzo"),
            ),
        ]

    def test_rate_pipeline(method: speech.Normalization):
        events = [
            Event(time_ms=100, duration_ms=300, chunks=["one"]),  # gap: 100ms
            Event(time_ms=500, duration_ms=400, chunks=["two."]),
            Event(time_ms=2_100, duration_ms=None, chunks=["three"]),
            Event(time_ms=2_500, duration_ms=None, chunks=["four"]),
            Event(time_ms=2_900, duration_ms=400, chunks=["five"]),  # gap: 1200ms
            Event(time_ms=4_500, duration_ms=400, chunks=["six."]),
        ]
        normalized = speech.normalize_speech(
            events=events, gap_ms=2000, length=6, method=method
        )
        assert normalized == [
            Event(time_ms=100, duration_ms=800, chunks=["One. #0.10# Two."]),
            Event(time_ms=2_100, duration_ms=None, chunks=["three"]),
            Event(time_ms=2_500, duration_ms=None, chunks=["four"]),
            Event(time_ms=2_900, duration_ms=2000, chunks=["Five. #1.20# Six."]),
        ]

    test_pipeline("break_ends_sentence")
    test_rate_pipeline("break_ends_sentence")
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
        voice=Voice("Bill"),
    )

    _, voices, _ = await speech.synthesize_events(
        events=[event_en_us],
        lang="en-US",
        output_dir=tmp_path,
    )

    (voice,) = voices

    assert voice.speech_rate == pytest.approx(0.87, abs=0.02)


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


@pytest.mark.asyncio
async def test_azure_speech_quality():
    azure_key, azure_region = env.get_azure_config()
    sample_ssml = (
        '<speak xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="http://www.w3.org/2001/mstts" '
        'xmlns:emo="http://www.w3.org/2009/10/emotionml" '
        'version="1.0" xml:lang="en-US">'
        '<voice name="en-US-JennyNeural">'
        '<prosody rate="0%" pitch="0%"> '
        "You can replace this text with any text you wish.You can either write in this "
        "text box or paste your own text here. Enjoy using Text to Speech! "
        "</prosody> </voice> </speak>"
    )
    import azure.cognitiveservices.speech as azure_tts

    with tempfile.NamedTemporaryFile() as output:
        speech_config = azure_tts.SpeechConfig(
            subscription=azure_key, region=azure_region
        )
        speech_config.set_speech_synthesis_output_format(
            azure_tts.SpeechSynthesisOutputFormat.Riff44100Hz16BitMonoPcm
        )
        audio_config = azure_tts.audio.AudioOutputConfig(filename=output.name)
        speech_synthesizer = azure_tts.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        result = speech_synthesizer.speak_ssml(sample_ssml)
        assert result.reason == azure_tts.ResultReason.SynthesizingAudioCompleted
        ((audio, *_), _) = media.probe(output.name)
        assert audio.num_channels == 1
        assert audio.sample_rate_hz == 44100
        assert audio.encoding == "LINEAR16"


def test_concat_events() -> None:
    e1 = Event(time_ms=0, chunks=["Hello"], duration_ms=1000)
    e2_short_break = Event(time_ms=1000, chunks=["world"], duration_ms=1000)
    e2_long_break = Event(time_ms=1050, chunks=["world"], duration_ms=1000)

    assert speech.concat_events(e1, e2_short_break, break_sentence=False) == Event(
        time_ms=0, duration_ms=2000, chunks=["Hello world"]
    )

    assert speech.concat_events(e1, e2_long_break, break_sentence=False) == Event(
        time_ms=0, duration_ms=2050, chunks=["Hello #0.05# world"]
    )

    assert speech.concat_events(e1, e2_long_break, break_sentence=True) == Event(
        time_ms=0, duration_ms=2050, chunks=["Hello. #0.05# World"]
    )


def test_break_phrase():
    expected = [
        [
            (
                "Queen Elizabeth the second had an unparalleled reign, the effect of which has been felt across the world.",  # noqa: E501
                1190,  # time_ms
                7000,  # duration_ms
            )
        ],
        [
            (
                "In her record-breaking 7 decades on the throne, she witnessed the end of the British Empire and welcomed radical societal shifts.",  # noqa: E501
                9200,
                8800,
            )
        ],
        [
            (
                "She was the first person in the UK to make a long distance phone call without an operator, the first monarch in the world to send an e-mail, and one of the first to tweet.",  # noqa: E501
                20230,
                9790,
            ),
            (
                "The Queen's reign was monumental in absolutely every sense.",
                30110,
                3270,
            ),
            (
                "It was peppered with superlatives.",
                33430,
                2330,
            ),
            (
                "She was the longest reigning British monarch.",
                35830,
                2450,
            ),
            (
                "Her head appeared on more coins than any other living monarch.",
                38550,
                3470,
            ),
            (
                "She was herself like a monument, unchanging.",
                42070,
                2930,
            ),
        ],
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

    assert [
        speech.break_phrase(text=text, words=words, lang="en-US")
        for text, words in phrases
    ] == expected
