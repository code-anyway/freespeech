import functools
import uuid
from freespeech.api.storage import doc
import pytest


@pytest.mark.asyncio
async def test_put_get_query():
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

    client = doc.google_firestore_client()
    put = functools.partial(doc.put, client, "test")
    get = functools.partial(doc.get, client, "test")
    query = functools.partial(doc.query, client, "test")

    await put(key_1, value_1)
    assert await get(key_1) == value_1

    await put(key_2, value_2)
    assert await query("num", "==", 1)
    assert await query("bool", "==", True)
    assert await query("str", "==", key_2) == [value_2]


@pytest.mark.asyncio
async def test_query():
    client = doc.google_firestore_client()
    docs = await doc.query(client,
                           coll="test",
                           attr="bool",
                           op="==",
                           value=True,
                           order=("num", "ASCENDING"),
                           limit=2)

    assert len(docs) == 2
    assert all([d["num"] == 1 for d in docs])

    docs = await doc.query(client,
                           coll="test",
                           attr="bool",
                           op="==",
                           value=True,
                           order=("num", "DESCENDING"),
                           limit=2)

    assert len(docs) == 2
    assert all([d["num"] == 2 for d in docs])
