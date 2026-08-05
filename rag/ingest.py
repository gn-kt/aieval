import glob
import os

import chromadb
from dotenv import load_dotenv

load_dotenv()

from rag.embedder import embed_batch

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
COLLECTION_NAME = "ai_agent_notes"
CHROMA_URL = os.getenv("CHROMA_URL", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

_DEFAULT_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "notes")


def _get_client() -> chromadb.ClientAPI:
    if CHROMA_URL:
        return chromadb.HttpClient(host=CHROMA_URL, port=CHROMA_PORT)
    persist_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    return chromadb.PersistentClient(path=persist_dir)


def _read_md_files(directory: str) -> list[dict]:
    files = []
    for fpath in glob.glob(os.path.join(directory, "*.md")):
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            files.append({"filename": os.path.basename(fpath), "content": content})
    return files


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _chunk_documents(directory: str) -> list[dict]:
    files = _read_md_files(directory)
    documents = []
    for finfo in files:
        chunks = _chunk_text(finfo["content"])
        for i, chunk in enumerate(chunks):
            documents.append({
                "chunk_id": f"{finfo['filename']}_chunk_{i}",
                "text": chunk,
                "metadata": {
                    "source": finfo["filename"],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })
    return documents


def ingest(directory: str | None = None, force: bool = False) -> int:
    if directory is None:
        directory = os.getenv("RAG_DOCS_DIR", _DEFAULT_DOCS_DIR)

    client = _get_client()

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    documents = _chunk_documents(directory)
    texts = [d["text"] for d in documents]
    ids = [d["chunk_id"] for d in documents]
    metadatas = [d["metadata"] for d in documents]

    embeddings = embed_batch(texts)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    return collection.count()


if __name__ == "__main__":
    count = ingest(force=True)
    print(f"Ingested {count} chunks")
