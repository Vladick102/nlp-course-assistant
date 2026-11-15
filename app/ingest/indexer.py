"""[DP] Build BM25 (lemmas) and dense (bge-m3) indexes over data/index/chunks.jsonl."""

from __future__ import annotations

import hashlib
import json
import pickle
import time

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import cfg, path
from app.store import chunks
from app.text import lemmas

MAX_SEQ_LEN = 256  # CPU budget: 512 tokens would take ~95 min for 3.5k chunks


def emb_key(model_name: str, max_seq_len: int, text: str) -> str:
    return hashlib.sha256(f"{model_name}\x00{max_seq_len}\x00{text}".encode()).hexdigest()


class _EmbCache:
    """Dense vectors keyed by sha256(model + max_seq_len + search_text): data/cache/emb/{vecs.npy,keys.json}."""

    def __init__(self, vecs: dict[str, np.ndarray]) -> None:
        self.vecs = vecs

    @staticmethod
    def _dir():
        d = path("cache") / "emb"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def load(cls) -> _EmbCache:
        d = cls._dir()
        if not (d / "vecs.npy").exists() or not (d / "keys.json").exists():
            return cls({})
        arr = np.load(d / "vecs.npy")
        keys = json.loads((d / "keys.json").read_text(encoding="utf-8"))
        return cls(dict(zip(keys, arr, strict=True)) if len(keys) == len(arr) else {})

    def save(self) -> None:
        d = self._dir()
        keys = list(self.vecs)
        np.save(d / "vecs.npy", np.stack([self.vecs[k] for k in keys]))
        (d / "keys.json").write_text(json.dumps(keys), encoding="utf-8")


def build() -> None:
    out = path("index")
    chunks.cache_clear()
    cs = list(chunks().values())
    ids = [c.chunk_id for c in cs]

    t = time.time()
    bm25 = BM25Okapi([lemmas(c.search_text) for c in cs])
    with open(out / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": ids}, f)
    print(f"bm25: {len(cs)} chunks in {time.time() - t:.1f}s")

    from sentence_transformers import SentenceTransformer

    model_name = cfg()["retrieval"]["embed_model"]
    keys = [emb_key(model_name, MAX_SEQ_LEN, c.search_text) for c in cs]
    cache = _EmbCache.load()
    todo = [i for i, k in enumerate(keys) if k not in cache.vecs]
    print(f"dense: {len(cs) - len(todo)} reused from cache, {len(todo)} to encode")
    t = time.time()
    if todo:
        model = SentenceTransformer(model_name, device="cpu")
        model.max_seq_length = MAX_SEQ_LEN
        print(f"dense: model loaded in {time.time() - t:.1f}s")
        t = time.time()
        # sort by length so batches are homogeneous (big CPU speedup)
        todo.sort(key=lambda i: len(cs[i].search_text))
        emb = model.encode(
            [cs[i].search_text for i in todo], batch_size=16, normalize_embeddings=True, show_progress_bar=True
        )
        for i, v in zip(todo, emb, strict=True):
            cache.vecs[keys[i]] = v.astype(np.float16)
        cache.save()
    full = np.stack([cache.vecs[k] for k in keys]).astype(np.float16)
    np.save(out / "dense.npy", full)
    (out / "chunk_ids.json").write_text(json.dumps(ids), encoding="utf-8")
    print(f"dense: encoded {len(todo)}, reused {len(cs) - len(todo)} (total {len(cs)}) in {time.time() - t:.1f}s")


if __name__ == "__main__":
    build()
