import pytest

from freespeech.lib import hash, media, speech
from freespeech.lib.storage import obj
from freespeech.types import Event

VIDEO_RU = "tests/lib/data/media/ru-RU.mp4"
VIDEO_EN = "tests/lib/data/media/en-US.mp4"
AUDIO_RU = "tests/lib/data/media/ru-RU-mono.wav"
AUDIO_EN = "tests/lib/data/media/en-US-mono.wav"
AUDIO_MIX_RU_EN = "tests/lib/data/media/mix-ru-RU-1-en-US-10.wav"
AUDIO_DUB_EN_RU = "tests/lib/data/media/dub-en-US-ru-RU.mp4"

AUDIO_RU_GS = "gs://freespeech-tests/test_media/ru-RU-mono.wav"


@pytest.mark.asyncio
async def test_multi_channel_audio_to_mono(tmp_path):
    output_mono = await media.multi_channel_audio_to_mono(VIDEO_EN, tmp_path)
    (audio, *_), _ = media.probe(output_mono)
    assert audio.num_channels == 1


@pytest.mark.asyncio
async def test_concat_and_pad(tmp_path):
    clips = [(10_000, AUDIO_RU), (20_000, AUDIO_RU)]

    (original_audio, *_), _ = media.probe(AUDIO_RU)
    output = await media.concat_and_pad(clips, tmp_path)
    (audio, *_), _ = media.probe(output)
    assert audio.duration_ms == 2 * original_audio.duration_ms + 30_000


@pytest.mark.asyncio
async def test_concat(tmp_path):
    clips = [AUDIO_RU] * 5
    (original_audio, *_), _ = media.probe(AUDIO_RU)

    output = await media.concat(clips, tmp_path)
    (audio, *_), _ = media.probe(output)

    epsilon = 1
    assert audio.duration_ms == 5 * original_audio.duration_ms + epsilon


@pytest.mark.asyncio
async def test_mix(tmp_path):
    files = (AUDIO_RU, AUDIO_EN)
    weights = (1, 10)
    output = await media.mix(files=files, weights=weights, output_dir=tmp_path)
    assert hash.file(output) == hash.file(AUDIO_MIX_RU_EN)


@pytest.mark.asyncio
async def test_dub(tmp_path):
    # Add RU dub over EN video
    output = await media.dub(VIDEO_EN, AUDIO_RU, tmp_path)

    # And confirm by transcribing it
    output_mono = await media.multi_channel_audio_to_mono(output, tmp_path)
    uri = await obj.put(output_mono, AUDIO_RU_GS)
    (audio, *_), _ = media.probe(output_mono)

    t_ru = await speech.transcribe(uri, audio, "ru-RU")
    assert t_ru == [Event(time_ms=0, duration_ms=3180, chunks=["123"])]


@pytest.mark.asyncio
async def test_cut(tmp_path):
    # Audio-only
    (audio, *_), _ = media.probe(AUDIO_EN)
    assert audio.duration_ms == 3264

    output = await media.cut(
        AUDIO_EN, start="00:00:01", finish="00:00:02", output_dir=tmp_path
    )

    (audio, *_), _ = media.probe(output)
    assert audio.duration_ms == 2_005

    # Video with audio track
    (audio, *_), (video, *_) = media.probe(VIDEO_EN)
    assert audio.duration_ms == 3277
    assert video.duration_ms == 3298

    output = await media.cut(
        VIDEO_EN, start="00:00:01", finish="00:00:02", output_dir=tmp_path
    )

    (audio, *_), (video, *_) = media.probe(output)
    assert audio.duration_ms == 2_000
    assert video.duration_ms == 2_032


@pytest.mark.asyncio
async def test_video_as_audio(tmp_path):
    audio = await media.multi_channel_audio_to_mono(AUDIO_DUB_EN_RU, tmp_path)
    ((audio_meta, *_), *_) = media.probe(audio)

    assert audio_meta.duration_ms == 3221
    assert audio_meta.encoding == "LINEAR16"