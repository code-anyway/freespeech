from freespeech.types import Stream


def test_stream():
    s = Stream(duration_ms=1, storage_url="gs://bucket/dir", suffix="foo")
    assert s.url == f"gs://bucket/dir/{s._id}.foo"

    s = Stream(duration_ms=1, storage_url="gs://bucket/dir/", suffix="foo")
    assert s.url == f"gs://bucket/dir/{s._id}.foo"

    s = Stream(duration_ms=1, storage_url="gs://bucket/dir//", suffix="foo")
    assert s.url == f"gs://bucket/dir/{s._id}.foo"

    s = Stream(duration_ms=1, storage_url="gs://bucket///", suffix="foo")
    assert s.url == f"gs://bucket/{s._id}.foo"
