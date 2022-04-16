from freespeech.api import hash, media, speech
from freespeech.api.storage import obj
from freespeech.types import Event

VIDEO_RU = "tests/api/data/media/ru-RU.mp4"
VIDEO_EN = "tests/api/data/media/en-US.mp4"
AUDIO_RU = "tests/api/data/media/ru-RU-mono.wav"
AUDIO_EN = "tests/api/data/media/en-US-mono.wav"
AUDIO_MIX_RU_EN = "tests/api/data/media/mix-ru-RU-1-en-US-10.wav"
AUDIO_DUB_EN_RU = "tests/api/data/media/dub-en-US-ru-RU.mp4"

AUDIO_RU_GS = "gs://freespeech-tests/test_media/ru-RU-mono.wav"


def test_probe():
    pass


def test_multi_channel_audio_to_mono(tmp_path):
    output_mono = media.multi_channel_audio_to_mono(VIDEO_EN, tmp_path)
    (audio, *_), _ = media.probe(output_mono)
    assert audio.num_channels == 1


def test_concat_and_pad(tmp_path):
    clips = [(10_000, AUDIO_RU), (20_000, AUDIO_RU)]

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
    output = media.mix(files=(AUDIO_RU, AUDIO_EN), weights=(1, 10), output_dir=tmp_path)
    assert hash.file(output) == hash.file(AUDIO_MIX_RU_EN)


def test_dub(tmp_path):
    # Add RU dub over EN video
    output = media.dub(VIDEO_EN, AUDIO_RU, tmp_path)

    # And confirm by transcribing it
    output_mono = media.multi_channel_audio_to_mono(output, tmp_path)
    uri = obj.put(output_mono, AUDIO_RU_GS)
    (audio, *_), _ = media.probe(output_mono)

    t_ru = speech.transcribe(uri, audio, "ru-RU")
    assert t_ru == [Event(time_ms=0, duration_ms=3180, chunks=["123"])]
