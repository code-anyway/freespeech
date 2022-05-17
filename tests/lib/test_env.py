from freespeech import env


def test_get_storage_url() -> None:
    assert not env.get_storage_url().endswith("/")
