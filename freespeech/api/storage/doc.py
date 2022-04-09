from contextlib import contextmanager
from typing import Dict, List, Literal

from google.cloud import firestore

from freespeech import env

QueryOperation = Literal["=="]


@contextmanager
def google_firestore_client():
    project_id = env.get_project_id()
    client = firestore.Client(project=project_id)
    try:
        yield client
    finally:
        # Some Google client libraries are leaking resources
        # https://github.com/googleapis/google-api-python-client/issues/618#issuecomment-669787286
        client._http.close()


def get(coll: str, key: str) -> Dict:
    with google_firestore_client() as client:
        doc = client.collection(coll).document(key)
        value = doc.get().to_dict()
    return value


def put(coll: str, key: str, value: Dict):
    with google_firestore_client() as client:
        doc = client.collection(coll).document(key)
        doc.set(value)


def query(coll: str, attr: str, op: QueryOperation, value: str) -> List[Dict]:
    with google_firestore_client() as client:
        query = client.collection(coll).where(attr, op, value)
        res = query.stream()
    return [item.to_dict() for item in res]
