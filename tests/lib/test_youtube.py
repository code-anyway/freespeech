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

BROKEN_DOWNLOAD_VIDEO = "https://www.youtube.com/watch?v=8xKCecfR-z8"


def test_broken_download(tmp_path):
    # The default video stream for this video won't download due to
    # http.client.IncompleteRead.
    audio_file, video_file, _, _ = youtube.download(
        BROKEN_DOWNLOAD_VIDEO, tmp_path, "test.audio", "test.video"
    )
    AUDIO_HASH = (
        "fc38b308bd03da71f0a3a27d41dd37281d24ed2a828c0f81a6f43b02b0679b9d",
        "9a9c1ed4484fa7242543b7bc34fe2bf60b6b0ae0f30a9fc4cccd5b6767f3b337",
    )
    VIDEO_HASH = (
        "cb1c94121b5c87cf9dbb819ad49145c9fb83e0042fcf1c39e6fbcdd3f72c85be",
        "6c7caedf0541d16c3d382fec41355b1226dd1d9121b81cf2e8bbc85aa904a3b6",
        "4caf22ef5eef77cdef4337abd60d36d7476502f6b37893bc0ecc53878d7989bc",
        "f96cb054fd52199437c57250d323108ba5f0753d2043de5e982fa486e65d8146",
    )
    assert hash.file(audio_file) in AUDIO_HASH
    assert hash.file(video_file) in VIDEO_HASH

    # some videos have streams with 'content-length' missing which causes
    # pytube to crash
    missing_content_length = "https://youtu.be/BoGEAwsHmr0"
    _, _, _, _ = youtube.download(
        missing_content_length,
        output_dir=tmp_path,
        audio_filename="test.audio",
        video_filename="test.video",
        max_retries=10,
    )


def test_download_local(tmp_path):
    audio_file, video_file, info, captions = youtube.download(
        VIDEO_URL, tmp_path, "test.audio", "test.video"
    )

    assert info.title == "Announcer's test"
    assert info.description == VIDEO_DESCRIPTION
    assert info.tags == ["announcer's", "test"]

    assert audio_file.suffix == ".audio"
    assert video_file.suffix == ".video"

    assert captions["en-US"][0] == Event(
        time_ms=480,
        duration_ms=6399,
        chunks=["one hand two ducks three squawking geese"],
    )

    assert (
        hash.file(audio_file)
        == "7b0dfb36784281f06c09011d631289f34aed8ba1cf0411b49d60c1d2594f7fe9"
    )
    assert hash.file(video_file) in (
        "0c2d95a0804c5223d714076f81afa929c65d04e833a7726d017f0405cac70ff0",
        "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297",
        "1a3f37fff7e3115f0cf5aad47d270b73af656ca52a54fb179d378360d6ce4656",
    )


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
