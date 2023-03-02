import json
from pathlib import Path

import pytest

from freespeech.lib import hash, youtube
from freespeech.types import Event

VIDEO_DESCRIPTION = (
    "One hen\n\n"
    "Two ducks\n\n"
    "Three squawking geese\n\n"
    "Four limerick oysters\n\n"
    "Five corpulent porpoises\n\n"
    "Six pairs of Don Alverzo's tweezers\n\n"
    "Seven thousand Macedonians in full battle array\n\n"
    "Eight brass monkeys from the ancient sacred crypts of Egypt\n\n"
    "Nine apathetic, sympathetic, diabetic old men on roller skates, "
    "with a marked propensity towards procrastination and sloth"
    ""
)
VIDEO_URL = "https://youtu.be/bhRaND9jiOA"
PRESIDENT_UA_DAY_55 = "https://www.youtube.com/watch?v=PRLIlthRIwA"
LEX_ZUCK = "https://www.youtube.com/watch?v=5zOHSysMmH0"

BROKEN_DOWNLOAD_VIDEO = "https://www.youtube.com/watch?v=8xKCecfR-z8"


@pytest.mark.asyncio
async def test_broken_download(tmp_path):
    # The default video stream for this video won't download due to
    # http.client.IncompleteRead.
    audio_file, video_file = await youtube.download(BROKEN_DOWNLOAD_VIDEO, tmp_path)

    assert hash.file(audio_file)
    assert video_file is not None, "video file should be downloaded"
    assert hash.file(video_file)

    # some videos have streams with 'content-length' missing which causes
    # pytube to crash
    missing_content_length = "https://youtu.be/BoGEAwsHmr0"
    _, _ = await youtube.download(
        missing_content_length,
        output_dir=tmp_path,
        max_retries=10,
    )


@pytest.mark.asyncio
async def test_download_local(tmp_path):
    audio_file, video_file = await youtube.download(
        VIDEO_URL,
        tmp_path,
    )

    meta = youtube.get_meta(VIDEO_URL)

    assert meta.title == "Announcer's test"
    assert meta.description == VIDEO_DESCRIPTION
    assert meta.tags == ["announcer's", "test"]

    assert Path(audio_file).suffix == ".webm"
    assert video_file is not None, "video file should be downloaded"
    assert Path(video_file).suffix == ".webm"

    captions = youtube.get_captions(VIDEO_URL, "en-US")

    assert captions[0] == Event(
        time_ms=480,
        duration_ms=6399,
        chunks=["one hand two ducks three squawking geese"],
    )

    assert hash.file(audio_file)
    assert hash.file(video_file)


def test_convert_captions():
    with open("tests/lib/data/youtube/captions_en.xml") as fd:
        en = "\n".join(fd.readlines())

    with open("tests/lib/data/youtube/captions_ru.xml") as fd:
        ru = "\n".join(fd.readlines())

    t = youtube.convert_captions([("en", en), ("ru", ru)])

    with open("tests/lib/data/youtube/transcript_en_US.json", encoding="utf-8") as fd:
        expected_en_US = [Event(**item) for item in json.load(fd)]

    with open("tests/lib/data/youtube/transcript_ru_RU.json", encoding="utf-8") as fd:
        expected_ru_RU = [Event(**item) for item in json.load(fd)]

    assert expected_en_US == t["en-US"]
    assert expected_ru_RU == t["ru-RU"]


def test_convert_captiions_with_no_duration():
    with open("tests/lib/data/youtube/captions_missing_duration_en.xml") as fd:
        en = "\n".join(fd.readlines())
    t = youtube.convert_captions([("en", en)])
    expected = {
        "en-US": [
            Event(time_ms=10, duration_ms=3000, chunks=["Every human"]),
            Event(time_ms=3010, duration_ms=1000, chunks=["Foo"]),
        ]
    }
    assert t == expected


def test_auto_captions():
    with open("tests/lib/data/youtube/captions_en.xml") as fd:
        en = "\n".join(fd.readlines())

    with open("tests/lib/data/youtube/auto-captions.xml") as fd:
        a_en = "\n".join(fd.readlines())

    with open("tests/lib/data/youtube/transcript_en_US.json", encoding="utf-8") as fd:
        expected_en_US = [Event(**item) for item in json.load(fd)]

    with open("tests/lib/data/youtube/auto-captions.json", encoding="utf-8") as fd:
        expected_a_en_US = [
            Event(
                **item,
            )
            for item in json.load(fd)
        ]

    t = youtube.convert_captions([("a.en", a_en)])
    assert t["en-US"] == expected_a_en_US

    t = youtube.convert_captions([("en", en), ("a.en", a_en)])
    assert t["en-US"] == expected_en_US, "regular captions should override automatic"

    t = youtube.convert_captions([("a.en", a_en), ("en", en)])
    assert t["en-US"] == expected_en_US, "regular captions should override automatic"
