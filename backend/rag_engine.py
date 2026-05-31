"""Local RAG engine using BAAI/bge-small-en-v1.5 embeddings + cosine search.
No external vector DB — stores everything in local JSON."""

import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

_EMB = None
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_FILE = os.path.join(DATA_DIR, "documents.json")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def _embedder():
    global _EMB
    if _EMB is None:
        _EMB = SentenceTransformer(EMBED_MODEL)
    return _EMB


def _load():
    if not os.path.exists(DOCS_FILE):
        return {}
    with open(DOCS_FILE) as f:
        return json.load(f)


def _save(docs):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DOCS_FILE, "w") as f:
        json.dump(docs, f)


def embed_text(text: str) -> list[float]:
    return _embedder().encode(text).tolist()


def index_document(user_id: str, chunks: list[dict]):
    docs = _load()
    docs.setdefault(user_id, [])
    for c in chunks:
        vec = embed_text(c["content"])
        docs[user_id].append({
            "content": c["content"],
            "metadata": c.get("metadata", {}),
            "embedding": vec,
        })
    _save(docs)


def query_context(user_id: str, query: str, top_k: int = 3) -> list[str]:
    docs = _load()
    entries = docs.get(user_id, [])
    if not entries:
        return []
    qv = np.array(embed_text(query))
    scores = [np.dot(qv, np.array(e["embedding"])) for e in entries]
    idx = np.argsort(scores)[-top_k:][::-1]
    return [
        f"[{entries[i]['metadata'].get('source', '?')}] {entries[i]['content']}"
        for i in idx
    ]


def has_documents(user_id: str) -> bool:
    return len(_load().get(user_id, [])) > 0


def count_chunks(user_id: str) -> int:
    return len(_load().get(user_id, []))
