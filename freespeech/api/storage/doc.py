from typing import Dict, List, Literal

from google.cloud import firestore

from freespeech import env

QueryOperator = Literal["=="]


def google_firestore_client() -> firestore.AsyncClient:
    project_id = env.get_project_id()
    client = firestore.AsyncClient(project=project_id)
    return client


async def get(client: firestore.Client, coll: str, key: str) -> Dict:
    doc = client.collection(coll).document(key)
    value = await doc.get()
    return value.to_dict()


async def put(client: firestore.Client, coll: str, key: str, value: Dict):
    doc = client.collection(coll).document(key)
    await doc.set(value)


async def query(client: firestore.Client,
                coll: str,
                attr: str,
                op: QueryOperator,
                value: str) -> List[Dict]:
    query = client.collection(coll).where(attr, op, value)
    return [item.to_dict() async for item in query.stream()]
