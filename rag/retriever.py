import os

import chromadb
from dotenv import load_dotenv

load_dotenv()

from rag.embedder import embed

CHROMA_URL = os.getenv("CHROMA_URL", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "ai_agent_notes"


def _get_client() -> chromadb.ClientAPI:
    if CHROMA_URL:
        return chromadb.HttpClient(host=CHROMA_URL, port=CHROMA_PORT)
    persist_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    return chromadb.PersistentClient(path=persist_dir)


def _get_collection() -> chromadb.Collection:
    client = _get_client()
    return client.get_collection(COLLECTION_NAME)


def _distance_to_score(distance: float) -> float:
    return max(0.0, 1.0 - distance)


def search(query: str, k: int = 3) -> list[dict]:
    query_embedding = embed(query)
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i in range(len(ids)):
        hits.append({
            "id": ids[i],
            "text": documents[i],
            "source": metadatas[i].get("source", "") if metadatas[i] else "",
            "chunk_index": metadatas[i].get("chunk_index", -1) if metadatas[i] else -1,
            "score": _distance_to_score(distances[i]),
        })
    return hits
