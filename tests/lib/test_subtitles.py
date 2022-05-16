from freespeech.lib import subtitles
from freespeech.types import Event


def test_srt():
    SRT_FILE = "tests/lib/data/subtitles/karlsson.srt"
    res = subtitles.srt(SRT_FILE)

    expected = [
        Event(
            time_ms=8484,
            duration_ms=5205,
            chunks=["Inspired by Astrid Lindgren's fairy tale."],
            voice=None,
        ),
        Event(
            time_ms=15383, duration_ms=4373, chunks=["Karlsson and The Kid"], voice=None
        ),
    ]
    assert res == expected
