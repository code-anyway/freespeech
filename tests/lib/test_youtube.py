from freespeech.lib import hash, youtube

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


def test_download_local(tmp_path):
    audio_file, video_file, info = youtube.download(VIDEO_URL, tmp_path)

    assert info.title == "Announcer's test"
    assert info.description == VIDEO_DESCRIPTION
    assert info.tags == ["announcer's", "test"]

    assert audio_file.suffix == ".webm"
    assert video_file.suffix == ".mp4"

    assert (
        hash.file(audio_file)
        == "7b0dfb36784281f06c09011d631289f34aed8ba1cf0411b49d60c1d2594f7fe9"
    )
    assert (
        hash.file(video_file)
        == "ebc0b0ecf95a540a47696626e60e4ce4bd47582fd6b866ce72e762e531b03297"
    )
