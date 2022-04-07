from freespeech import language, speech, services, datastore
from freespeech.notion import client
from freespeech.types import Transcript, Event


TEXT = [
    "One hen.\n\n",
    "Two ducks.\n\n",
    "Three squawking geese.\n\n",
    "Four limerick oysters.\n\n",
    "Five corpulent porpoises\n\n",
    "Six pairs of Don Alverzo's tweezers.\n\n",
    "Seven thousand Macedonians in full battle array.\n\n",
    "Eight brass monkeys from the ancient sacred crypts of Egypt.\n\n",
    "Nine apathetic, sympathetic, diabetic old men on roller skates, "
    "with a marked propensity towards procrastination and sloth."""
]


def test_translate_synthesize():
    transcript = language.translate(
        text=Transcript(
            lang="en-US",
            events=[Event(
                time_ms=0,
                duration_ms=30_000,
                chunks=TEXT
            )]
        ),
        source=None,
        target="ru-RU"
    )

    audio = speech.synthesize(
        transcript=transcript,
        voice="ru-RU-WaveNet-A",
        storage_url="gs://freespeech-tests/e2e/"
    )

    assert abs(audio.duration_ms - 30_000) < 500


def test_download_transcribe_translate_synthesize_voiceover(
    monkeypatch, datastore_emulator
):
    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "gs://freespeech-tests/e2e/")

    url = "https://youtu.be/bhRaND9jiOA"
    transcript_id = services.download_and_transcribe(url, "en-US")
    translated_id = services.translate(transcript_id, lang="ru-RU")
    audio_id = services.synthesize(translated_id)
    voiceover_id = services.voiceover(url, audio_id)
    res = datastore.get(voiceover_id, "media")
    assert res is None


def test_voiceover_from_notion(
    monkeypatch, datastore_emulator
):
    PAGE_IDs = [
        "828608b4f74840f5bbf22994a05693a9",  # Z. UN Eng
        "de941561352b4b9d90e4d3c03936e6c9",  # Z. UN Rus
        "03182244413246de9d632b9e59548718",  # Announcer Test Eng
        "cb40a2e3cf3b4277b8d08e779c5ed306",  # Announcer Test Rus
    ]

    monkeypatch.setenv("FREESPEECH_STORAGE_URL", "gs://freespeech-tests/e2e/")

    media = [
        services.create_voiceover_from_notion_page(page_id)
        for page_id in PAGE_IDs
    ]

    print(media)

    assert False
