from freespeech.api import media, hash


VIDEO_RU = "tests/api/data/media/ru-RU.mp4"
VIDEO_EN = "tests/api/data/media/en-US.mp4"
AUDIO_RU = "tests/api/data/media/ru-RU-mono.wav"
AUDIO_EN = "tests/api/data/media/en-US-mono.wav"
AUDIO_MIX_RU_EN = "tests/api/data/media/mix-ru-RU-1-en-US-10.wav"
AUDIO_DUB_EN_RU = "tests/api/data/media/dub-en-US-ru-RU.mp4"


def test_probe():
    pass


def test_multi_channel_audio_to_mono(tmp_path):
    output_mono = media.multi_channel_audio_to_mono(VIDEO_EN, tmp_path)
    (audio, *_), _ = media.probe(output_mono)
    assert audio.num_channels == 1

    output = media.multi_channel_audio_to_mono(output_mono, tmp_path)
    assert output == output_mono


def test_concat_and_pad(tmp_path):
    clips = [
        (10_000, AUDIO_RU),
        (20_000, AUDIO_RU)
    ]

    (original_audio, *_), _ = media.probe(AUDIO_RU)
    output = media.concat_and_pad(clips, tmp_path)
    (audio, *_), _ = media.probe(output)
    assert audio.duration_ms == 2 * original_audio.duration_ms + 30_000


def test_concat(tmp_path):
    clips = [AUDIO_RU] * 5
    (original_audio, *_), _ = media.probe(AUDIO_RU)

    output = media.concat(clips, tmp_path)
    (audio, *_), _ = media.probe(output)

    epsilon = 1
    assert audio.duration_ms == 5 * original_audio.duration_ms + epsilon


def test_mix(tmp_path):
    clips = [
        (AUDIO_RU, 1),
        (AUDIO_EN, 10)
    ]

    output = media.mix(clips, tmp_path)
    assert hash.file(output) == hash.file(AUDIO_MIX_RU_EN)


def test_dub(tmp_path):
    output = media.dub(VIDEO_EN, AUDIO_RU, tmp_path)
    assert hash.file(output) == hash.file(AUDIO_DUB_EN_RU)
