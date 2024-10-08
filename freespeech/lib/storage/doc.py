from typing import Any, Dict, List, Literal, Tuple

from google.cloud import firestore  # type: ignore

from freespeech import env

QueryOperator = Literal["=="]
QueryOrder = Literal["ASCENDING", "DESCENDING"]


field = str


def google_firestore_client() -> firestore.AsyncClient:
    project_id = env.get_project_id()
    client = firestore.AsyncClient(project=project_id)
    return client


async def get(
    client: firestore.AsyncClient, coll: str, key: str
) -> Dict[str, Any] | None:
    doc = client.collection(coll).document(key)
    value = await doc.get()
    res = value.to_dict()
    if isinstance(res, Dict):
        return value.to_dict()
    else:
        return None


async def put(
    client: firestore.AsyncClient, coll: str, key: str, value: Dict[Any, Any]
) -> None:
    doc = client.collection(coll).document(key)
    await doc.set(value)


async def query(
    client: firestore.AsyncClient,
    coll: str,
    attr: str,
    op: QueryOperator,
    value: str,
    order: Tuple[field, QueryOrder] | None = None,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    query = client.collection(coll).where(
        field_path=attr, op_string=op, value=value, filter=None
    )

    # https://github.com/astaff/freespeech/issues/1 will resolve this
    # query = query.order_by(field, direction=direction) if order else query
    # query = query.limit(limit) if limit else query
    items = [item.to_dict() async for item in query.stream()]

    if order:
        field, direction = order
        from operator import itemgetter

        items = list(
            sorted(items, key=itemgetter(field), reverse=(direction == "DESCENDING"))
        )
        if limit:
            return items[:limit]
        else:
            return items
    else:
        return items
