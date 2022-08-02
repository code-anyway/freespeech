import json
from uuid import uuid4

from freespeech.lib import tasks


def test_schedule():
    url = "https://transcript-qux7zlmkmq-uc.a.run.app/transcript/synthesize"

    payload = {
        "transcript": {
            "lang": "en-US",
            "events": [{"time_ms": 0, "chunks": [str(uuid4())]}],
        }
    }

    task = tasks.schedule(
        method="POST", url=url, payload=json.dumps(payload).encode("utf-8")
    )

    assert task.state == "Pending"
    assert task.id
