import pytest

from freespeech.api import synthesize
from freespeech.types import Event, Settings, Transcript, Voice

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
    audio = await synthesize.synthesize(test_ru)

    assert audio
    assert audio.endswith(".wav")
    assert audio.startswith("gs://")
