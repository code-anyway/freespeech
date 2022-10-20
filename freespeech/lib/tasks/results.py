from freespeech.lib.storage import doc
from freespeech.types import Task


async def get(id: str) -> Task:
    doc_client = doc.google_firestore_client()
    result = await doc.get(doc_client, "results", id)
    if not result:
        raise ValueError(f"Task not found: {id}")
    if result["status"] > 400 or result["status"] == 299:
        return Task(state="Failed", id=id, result=result["result"])
    else:
        return Task(state="Done", id=id, result=result["result"])
