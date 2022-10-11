import pytest

from freespeech.lib import audio, media, speech
from freespeech.types import Voice


@pytest.mark.asyncio
async def test_strip(tmp_path):
    file, _ = await speech.synthesize_text(
        "Hello world!",
        voice=Voice(character="Bill"),
        duration_ms=None,
        lang="en-US",
        output_dir=tmp_path,
    )
    ((audio_info, *_), *_) = media.probe(file)
    ((stripped_audio_info, *_), *_) = media.probe(audio.strip(file))
    assert audio_info.duration_ms - stripped_audio_info.duration_ms == 803


def test_silence(tmp_path):
    file = audio.silence(2345, tmp_path)
    assert media.audio_duration(file) == 2345
