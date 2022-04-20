from freespeech import env


def test_get_storage_url():
    assert not env.get_storage_url().endswith("/")
