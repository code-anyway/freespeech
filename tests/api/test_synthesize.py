from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from freespeech.api import synthesize
from freespeech.lib import hash, media, speech
from freespeech.lib.storage import obj
from freespeech.typing import Event, Settings, Transcript, Voice

AUDIO_BLANK = Path("tests/lib/data/ask/audio-blank-blanked.wav")
AUDIO_BLANK_SYNTHESIZED = Path("tests/lib/data/ask/audio-blank-synthesized.wav")
AUDIO_FILL = Path("tests/lib/data/ask/audio-fill-filled.wav")
AUDIO_FILL_SYNTHESIZED = Path("tests/lib/data/ask/audio-fill-synthesized.wav")

ANNOUNCERS_TEST_TRANSCRIPT_RU = Transcript(
    settings=Settings(),
    lang="ru-RU",
    events=[
        Event(
            time_ms=0,
            duration_ms=29000,
            voice=Voice(character="Alonzo"),
            chunks=[
                "Одна курица. Две утки. Три кричащих гуся. Четыре "
                "лимерик устрицы. Пять тучных дельфинов. Шесть пар "
                "пинцетов Дона Альверзо. Семь тысяч македонцев в "
                "полном боевом строю. Восемь латунных обезьян из "
                "древних священных склепов Египта. Девять апатичных, "
                "сочувствующих стариков-диабетиков на роликовых "
                "коньках с заметной склонностью к прокрастинации и "
                "лени."
            ],
        )
    ],
)


@pytest.mark.asyncio
async def test_synthesize_basic() -> None:
    test_ru = Transcript(
        lang="ru-RU",
        events=[
            Event(
                time_ms=0,
                chunks=["Путин хуйло!"],
            )
        ],
    )
    audio = await synthesize.dub(test_ru, is_smooth=False)

    assert audio
    assert audio.endswith(".wav")
    assert audio.startswith("https://")


@pytest.mark.asyncio
async def test_synthesize() -> None:
    test_doc = "https://docs.google.com/document/d/1kiSbMxcs2PUAeurKYZFXnT20AS77uvKfBi0j1w8eRzw/edit#"  # noqa: E501
    url = await synthesize.dub(test_doc, is_smooth=False)
    assert url


@pytest.mark.asyncio
async def test_synthesize_crop() -> None:
    test_doc = "https://docs.google.com/document/d/1HpH-ZADbAM8AzluFWO8ZTOkEoRobAvQ13rrCsK6SU-U/edit?usp=sharing"  # noqa: E501
    url = await synthesize.dub(test_doc, is_smooth=False)

    with TemporaryDirectory() as tmp_dir:
        transcript_str = await obj.get(obj.storage_url(url), dst_dir=tmp_dir)
        (audio_info, *_), _ = media.probe(transcript_str)
        assert audio_info.duration_ms / 1000.0 == pytest.approx(26.92, 0.12)


@pytest.mark.asyncio
async def test_synthesize_blank(monkeypatch) -> None:
    async def synthesize_events(*args, **kwargs):
        return [
            AUDIO_BLANK_SYNTHESIZED,
            [
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            ],
            [
                ("blank", 0, 2000),
                ("event", 2000, 6329),
                ("blank", 6329, 15000),
                ("event", 15000, 20116),
            ],
            True,
        ]

    monkeypatch.setattr(speech, "synthesize_events", synthesize_events)
    test_doc = "https://docs.google.com/document/d/1CvjpOs5QEe_mmAc5CEGRVNV68qDjdQipCDb2ge6OIn4/edit?usp=sharing"  # noqa: E501
    url = await synthesize.dub(test_doc, is_smooth=False)

    with TemporaryDirectory() as tmp_dir:
        transcript_str = await obj.get(obj.storage_url(url), dst_dir=tmp_dir)
        downmixed_audio = await media.multi_channel_audio_to_mono(
            transcript_str, tmp_dir
        )
        assert hash.file(downmixed_audio) in (
            hash.file(AUDIO_BLANK),
            "1ad6fdf7c5504c3e7d9bb178db857a5d18fdd79b312228b74acc1f6172b75ae9",
        )  # noqa: E501


@pytest.mark.asyncio
async def test_synthesize_fill(monkeypatch) -> None:
    async def synthesize_events(*args, **kwargs):
        return [
            AUDIO_FILL_SYNTHESIZED,
            [
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
                Voice(character="Ada", pitch=0.0, speech_rate=1.0),
            ],
            [
                ("blank", 0, 2000),
                ("event", 2000, 9239),
                ("blank", 9239, 15000),
                ("event", 15000, 21245),
            ],
            True,
        ]

    monkeypatch.setattr(speech, "synthesize_events", synthesize_events)

    test_doc = "https://docs.google.com/document/d/11WOfJZi8pqpj7_BLPy0uq9h1R0f_n-dJ11LPOBvPtQA/edit?usp=sharing"  # noqa: E501
    url = await synthesize.dub(test_doc, is_smooth=False)

    with TemporaryDirectory() as tmp_dir:
        transcript_str = await obj.get(obj.storage_url(url), dst_dir=tmp_dir)
        downmixed_audio = await media.multi_channel_audio_to_mono(
            transcript_str, tmp_dir
        )
        assert hash.file(downmixed_audio) in (
            hash.file(AUDIO_FILL),
            "dfd8817aebe33652a873fa61d51526062e73e87c0a03523b527dd2ac09edb5ef",
        )  # noqa: E501


@pytest.mark.asyncio
@pytest.mark.skip
async def test_synthesize_smooth() -> None:
    test_doc = "https://docs.google.com/document/d/1FcpUuLBv-yOfkJkMo2ltzqyr716b0zN3ftRwlkvbCVs/edit#"  # noqa: E501
    url = await synthesize.dub(test_doc, is_smooth=True)
    assert url
