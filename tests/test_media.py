from freespeech import media
from freespeech.types import Audio


SPEECH_STORAGE_URL = "gs://freespeech-tests/streams/"
SPEECH_ID = "43ec9404-13c4-4133-9fd9-c7b57263158f"
SPEECH_SUFFIX = "webm"
TEST_AUDIO = Audio(
    duration_ms=29_318,
    storage_url=SPEECH_STORAGE_URL,
    suffix=SPEECH_SUFFIX,
    _id=SPEECH_ID,
    encoding="WEBM_OPUS",
    sample_rate_hz=48_000,
    num_channels=2,
    lang="en-US"
)


def test_downmix_stereo_to_mono(tmp_path):
    local_storage_url = f"file://{tmp_path}"
    audio = media.downmix_stereo_to_mono(TEST_AUDIO, local_storage_url)

    assert audio.url == f"{local_storage_url}/{audio._id}.{audio.suffix}"
    info, = media.probe(audio.url)

    assert info.num_channels == 1
    assert info.suffix == "webm"


def test_concat(tmp_path):
    audio = media.concat(
        [
            (5_000, TEST_AUDIO),
            (10_000, TEST_AUDIO)
        ]
    )

    info, = media.probe(audio.url)
    assert info.duration_ms == TEST_AUDIO.duration_ms + 15_000

    audio = media.concat(
        [
            (0, TEST_AUDIO),
            (0, TEST_AUDIO)
        ]
    )

    info, = media.probe(audio.url)
    assert info.duration_ms == TEST_AUDIO.duration_ms
