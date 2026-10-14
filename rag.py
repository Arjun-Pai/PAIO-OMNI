# PAIO-Omni · rag.py  v3.1
"""
Semantic search over the Brain vault, replacing memory.py's old keyword
overlap entirely — every tier, no fallback (per Arjun's call).

  - Embeddings: sentence-transformers, all-MiniLM-L6-v2 (small, fast,
    CPU-friendly — good fit even for cpu_tiny).
  - Store: chromadb, persisted at <vault_path>/.rag_index/.
  - Indexing is incremental: <vault_path>/.rag_index/mtimes.json tracks
    each note's last-indexed mtime, so an unchanged note costs nothing
    on the next boot. A changed note has its old chunks deleted (by
    path metadata) before re-embedding, so nothing goes stale/duplicated.

Public API:
  update_index(vault_path)                        -> int (notes re-embedded)
  semantic_search(vault_path, query_text, top_k=3) -> str (### path\\ncontent blocks)
"""

import json
import os

import memory

_MODEL_NAME = "all-MiniLM-L6-v2"
_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50
_COLLECTION_NAME = "vault_notes"

_model = None
_clients = {}  # vault_path -> chroma client, cached per process


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _index_dir(vault_path: str) -> str:
    d = os.path.join(vault_path, ".rag_index")
    os.makedirs(d, exist_ok=True)
    return d


def _get_client(vault_path: str):
    if vault_path not in _clients:
        import chromadb
        _clients[vault_path] = chromadb.PersistentClient(path=_index_dir(vault_path))
    return _clients[vault_path]


def _get_collection(vault_path: str):
    client = _get_client(vault_path)
    return client.get_or_create_collection(_COLLECTION_NAME)


def _mtimes_path(vault_path: str) -> str:
    return os.path.join(_index_dir(vault_path), "mtimes.json")


def _load_mtimes(vault_path: str) -> dict:
    p = _mtimes_path(vault_path)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_mtimes(vault_path: str, mtimes: dict) -> None:
    try:
        with open(_mtimes_path(vault_path), "w", encoding="utf-8") as f:
            json.dump(mtimes, f, indent=2)
    except Exception as e:
        print(f"  [rag] could not save mtimes.json: {e}")


def _chunk(text: str) -> list:
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + _CHUNK_SIZE, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - _CHUNK_OVERLAP
    return chunks


def update_index(vault_path: str) -> int:
    """Incremental (re-)index. Safe to call on every boot — cheap when
    nothing changed. Returns how many notes were actually re-embedded."""
    if not vault_path:
        return 0

    try:
        collection = _get_collection(vault_path)
    except Exception as e:
        print(f"  [rag] could not open index (embeddings disabled this run): {e}")
        return 0

    mtimes = _load_mtimes(vault_path)
    notes = memory.list_notes(vault_path)
    reembedded = 0

    for rel in notes:
        full_path = memory.note_full_path(vault_path, rel)
        try:
            current_mtime = os.path.getmtime(full_path)
        except OSError:
            continue

        if mtimes.get(rel) == current_mtime:
            continue  # unchanged since last index — skip

        content = memory.read_note(vault_path, rel)
        chunks = _chunk(content)

        try:
            collection.delete(where={"path": rel})
        except Exception:
            pass  # nothing to delete yet, or backend quirk — fine either way

        if chunks:
            try:
                model = _get_model()
                embeddings = model.encode(chunks).tolist()
                ids = [f"{rel}::chunk{i}" for i in range(len(chunks))]
                metadatas = [{"path": rel, "chunk": i} for i in range(len(chunks))]
                collection.upsert(
                    ids=ids, embeddings=embeddings,
                    documents=chunks, metadatas=metadatas,
                )
            except Exception as e:
                print(f"  [rag] failed to embed {rel}: {e}")
                continue

        mtimes[rel] = current_mtime
        reembedded += 1

    # Drop entries for notes that no longer exist.
    for rel in list(mtimes.keys()):
        if rel not in notes:
            try:
                collection.delete(where={"path": rel})
            except Exception:
                pass
            del mtimes[rel]

    _save_mtimes(vault_path, mtimes)
    return reembedded


def semantic_search(vault_path: str, query_text: str, top_k: int = 3) -> str:
    """Drop-in replacement for the old relevant_notes(): same
    '### path\\ncontent' block format, so callers don't need to change."""
    if not vault_path or not query_text:
        return ""

    try:
        collection = _get_collection(vault_path)
        if collection.count() == 0:
            return ""
        model = _get_model()
        query_embedding = model.encode([query_text]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=top_k)
    except Exception as e:
        print(f"  [rag] semantic search unavailable this turn: {e}")
        return ""

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    if not documents:
        return ""

    # Group chunks by source note so one note's hits render as one block.
    by_path = {}
    for doc, meta in zip(documents, metadatas):
        path = meta.get("path", "unknown")
        by_path.setdefault(path, []).append(doc)

    blocks = [f"### {path}\n" + "\n...\n".join(chunks) for path, chunks in by_path.items()]
    return "\n\n".join(blocks)
