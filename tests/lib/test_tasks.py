import asyncio
import json
from uuid import uuid4

import pytest

from freespeech.lib.tasks import cloud_tasks


@pytest.mark.skip(reason="Remove after deployment (20220803)")
@pytest.mark.asyncio
async def test_schedule():
    url = "https://transcript-qux7zlmkmq-uc.a.run.app/transcript/translate"

    payload = {
        "transcript": {
            "lang": "en-US",
            "events": [{"time_ms": 0, "chunks": [str(uuid4())]}],
        },
        "lang": "ru-RU",
    }

    task = await cloud_tasks.schedule(
        method="POST", url=url, payload=json.dumps(payload).encode("utf-8")
    )

    assert task.state == "Pending"
    await asyncio.sleep(10.0)
    task = await cloud_tasks.get(task.id)
    assert task.state == "Done"
    assert task.result
