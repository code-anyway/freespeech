import functools
import uuid
from freespeech.api.storage import doc


def test_put_get_query():
    key_1 = str(uuid.uuid4())
    value_1 = {
        "num": 1,
        "list": ["a", "b", "c"],
        "str": key_1,
        "bool": True
    }

    key_2 = str(uuid.uuid4())
    value_2 = {
        "num": 2,
        "list": ["d", "e", "f"],
        "str": key_2,
        "bool": True,
    }

    put = functools.partial(doc.put, "test")
    get = functools.partial(doc.get, "test")
    query = functools.partial(doc.query, "test")

    put(key_1, value_1)
    assert get(key_1) == value_1

    put(key_2, value_2)
    assert len(query("num", "==", 1)) >= 1
    assert len(query("bool", "==", True)) >= 2
    assert query("str", "==", key_2) == [value_2]
