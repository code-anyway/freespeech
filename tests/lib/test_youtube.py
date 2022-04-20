import json

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


def test_download_local(tmp_path):
    audio_file, video_file, info, captions = youtube.download(VIDEO_URL, tmp_path)

    assert info.title == "Announcer's test"
    assert info.description == VIDEO_DESCRIPTION
    assert info.tags == ["announcer's", "test"]

    assert audio_file.suffix == ".webm"
    assert video_file.suffix == ".mp4"

    # TODO (astaff): add captions to test video or create a new one with captions.
    assert captions == {}

    assert (
        hash.file(audio_file)
        == "7b0dfb36784281f06c09011d631289f34aed8ba1cf0411b49d60c1d2594f7fe9"
    )
    assert (
        hash.file(video_file)
        == "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"
    )


def test_convert_captions():
    with open("tests/lib/data/youtube/captions_en.xml") as fd:
        en = "\n".join(fd.readlines())
    with open("tests/lib/data/youtube/captions_uk.xml") as fd:
        uk = "\n".join(fd.readlines())

    t = youtube.convert_captions([("en", en), ("uk", uk)])

    with open("tests/lib/data/youtube/transcript_en_US.json", encoding="utf-8") as fd:
        expected_en_US = [Event(**item) for item in json.load(fd)]
    with open("tests/lib/data/youtube/transcript_uk_UK.json", encoding="utf-8") as fd:
        expected_uk_UK = [Event(**item) for item in json.load(fd)]

    assert expected_en_US == t["en-US"]
    assert expected_uk_UK == t["uk-UK"]
