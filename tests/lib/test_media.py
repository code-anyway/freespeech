import pytest

from freespeech.lib import hash, media, speech

VIDEO_RU = "tests/lib/data/media/ru-RU.mp4"
VIDEO_EN = "tests/lib/data/media/en-US.mp4"
VIDEO_POTATO = "tests/lib/data/media/potato-video.mp4"
VIDEO_CROPPED_POTATO = "tests/lib/data/media/cropped-potato-video.mp4"
AUDIO_CROPPED_POTATO = "tests/lib/data/media/cropped-potato-audio.wav"

AUDIO_RU = "tests/lib/data/media/ru-RU-mono.wav"
AUDIO_EN = "tests/lib/data/media/en-US-mono.wav"
AUDIO_MIX_RU_EN = "tests/lib/data/media/mix-ru-RU-1-en-US-10.wav"
AUDIO_DUB_EN_RU = "tests/lib/data/media/dub-en-US-ru-RU.mp4"

AUDIO_RU_GS = "gs://freespeech-tests/test_media/ru-RU-mono.wav"
AUDIO_POTATO = "tests/lib/data/media/dubstep-audio.mp3"
AUDIO_DUBSTEP = "tests/lib/data/media/potato-audio.mp3"
AUDIO_MIX_DUBSTEP_POTATO = "tests/lib/data/media/mix-dubstep-potato.wav"
AUDIO_MIX_DUBSTEP_POTATO_NOOP = "tests/lib/data/media/mix-dubstep-audio-noop.wav"


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
    assert hash.file(output) in (
        hash.file(AUDIO_MIX_RU_EN),
        "3af33d52d676f711d5d505877131767bdda4776c7927701823be441608cca337",  # astaff
    )


@pytest.mark.asyncio
async def test_mix_spans(tmp_path):
    weights = (3, 10)
    synth_stream = media.mix_spans(
        original=AUDIO_DUBSTEP,
        synth_file=AUDIO_POTATO,
        spans=[
            ("blank", 0, 5000),
            ("event", 5000, 10000),
            ("blank", 10000, 20000),
        ],
        weights=weights,
    )
    synth_file = await media.write_streams(
        streams=[synth_stream], output_dir=tmp_path, extension="wav"
    )
    assert hash.file(synth_file) in (
        hash.file(AUDIO_MIX_DUBSTEP_POTATO),
        "20be60afa1d3f6b1b2d3da852f1d6e7d48e21a7ae6e43b243c7037a6f47e3401",  # astaff
    )

    # still op :(
    synth_stream = media.mix_spans(
        original=AUDIO_DUBSTEP,
        synth_file=AUDIO_POTATO,
        spans=[],
        weights=weights,
    )
    synth_file = await media.write_streams(
        streams=[synth_stream], output_dir=tmp_path, extension="wav"
    )

    assert hash.file(synth_file) in (
        hash.file(AUDIO_MIX_DUBSTEP_POTATO_NOOP),
        "5fff749bfc67c0a059b3d771338cad606a524b643e54d464499ea273fe934571",  # astaff
    )


@pytest.mark.asyncio
async def test_keep_events(tmp_path):
    # both
    out = await media.keep_events(
        file=VIDEO_POTATO,
        spans=[
            ("event", 1000, 10000),
            ("blank", 10000, 15000),
            ("event", 15000, 20000),
        ],
        output_dir=tmp_path,
        mode="both",
    )
    # assert hash.file(out) == hash.file(VIDEO_CROPPED_POTATO)
    assert media.probe(out)[0][0].duration_ms == pytest.approx(14047, 16)
    assert media.probe(out)[1][0].duration_ms == pytest.approx(14047, 16)

    # just audio
    out = await media.keep_events(
        file=VIDEO_POTATO,
        spans=[
            ("event", 1000, 10000),
            ("blank", 10000, 15000),
            ("event", 15000, 20000),
        ],
        output_dir=tmp_path,
        mode="audio",
    )
    assert media.probe(out)[0][0].duration_ms == pytest.approx(14000, 16)


@pytest.mark.asyncio
async def test_dub(tmp_path) -> None:
    # Add RU dub over EN video
    output = await media.dub(VIDEO_EN, AUDIO_RU, tmp_path)

    # And confirm by transcribing it
    output_mono = await media.multi_channel_audio_to_mono(output, tmp_path)

    t_ru = await speech.transcribe(
        output_mono, "ru-RU", provider="Google", model="latest_long"
    )
    event, *tail = t_ru
    assert not tail, "Expected only one event sequence."
    assert event.time_ms == 0
    assert event.duration_ms == pytest.approx(3180, abs=10)
    assert event.chunks == ["1 2 3"]


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
