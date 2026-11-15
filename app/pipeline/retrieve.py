"""[MOD] Hybrid retrieval: BM25 (lemmas + glossary) + dense (bge-m3), course filter, RRF fusion."""

from __future__ import annotations

import pickle
from functools import cache

import numpy as np
import yaml

from app.config import ROOT, cfg, path
from app.schemas import Hit
from app.store import chunks
from app.text import lemmas


@cache
def _bm25() -> tuple:
    with open(path("index") / "bm25.pkl", "rb") as f:
        d = pickle.load(f)
    return d["bm25"], d["chunk_ids"]


@cache
def _dense() -> tuple[np.ndarray, list[str]]:
    import json

    emb = np.load(path("index") / "dense.npy").astype(np.float32)
    ids = json.loads((path("index") / "chunk_ids.json").read_text(encoding="utf-8"))
    return emb, ids


@cache
def _embedder():
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer(cfg()["retrieval"]["embed_model"], device="cpu")
    m.max_seq_length = 512
    return m


@cache
def _glossary() -> list[tuple[str, str, set[str], set[str]]]:
    """(ua, en, lemma-set(ua), lemma-set(en)) per pair."""
    with open(ROOT / "data" / "glossary.yaml", encoding="utf-8") as f:
        pairs = yaml.safe_load(f)["pairs"]
    return [(ua, en, set(lemmas(ua)), set(lemmas(en))) for ua, en in pairs]


def expand_query(q: str) -> str:
    """Append counterpart terms for glossary entries found in the query (BM25 side only)."""
    ql = set(lemmas(q))
    extra: list[str] = []
    for ua, en, ua_l, en_l in _glossary():
        if ua_l and ua_l <= ql and not en_l <= ql:
            extra.append(en)
        elif en_l and en_l <= ql and not ua_l <= ql:
            extra.append(ua)
    return " ".join([q, *extra]) if extra else q


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over ranked id lists; returns (id, score) sorted desc."""
    scores: dict[str, float] = {}
    for r in rankings:
        for pos, cid in enumerate(r):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + pos + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def _allowed(ids: list[str], course: str | None, include_logistics: bool) -> np.ndarray:
    cs = chunks()
    return np.array(
        [(course is None or course in cs[i].courses) and (include_logistics or cs[i].kind != "logistics") for i in ids],
        dtype=bool,
    )


def _top(scores: np.ndarray, mask: np.ndarray, ids: list[str], k: int) -> list[tuple[str, float]]:
    s = np.where(mask, scores, -np.inf)
    idx = np.argpartition(-s, min(k, len(s) - 1))[:k]
    idx = idx[np.argsort(-s[idx])]
    return [(ids[i], float(s[i])) for i in idx if np.isfinite(s[i])]


def bm25_search(
    q: str, course: str | None, k: int, include_logistics: bool = False, glossary: bool | None = None
) -> list[tuple[str, float]]:
    bm25, ids = _bm25()
    if cfg()["retrieval"].get("use_glossary") if glossary is None else glossary:
        q = expand_query(q)
    toks = lemmas(q)
    if not toks:
        return []
    scores = np.asarray(bm25.get_scores(toks))
    return [(i, s) for i, s in _top(scores, _allowed(ids, course, include_logistics), ids, k) if s > 0]


def dense_search(q: str, course: str | None, k: int, include_logistics: bool = False) -> list[tuple[str, float]]:
    emb, ids = _dense()
    qv = _embedder().encode([q], normalize_embeddings=True)[0].astype(np.float32)
    return _top(emb @ qv, _allowed(ids, course, include_logistics), ids, k)


def run(
    queries: list[str],
    course: str | None,
    k: int | None = None,
    mode: str = "hybrid",
    include_logistics: bool = False,
    use_glossary: bool | None = None,
) -> list[Hit]:
    r = cfg()["retrieval"]
    k = k or r["fused_k"]
    queries = [q for q in queries if q and q.strip()]
    rankings: list[list[str]] = []
    if mode in ("bm25", "hybrid"):
        rankings += [
            [i for i, _ in bm25_search(q, course, r["bm25_k"], include_logistics, use_glossary)] for q in queries
        ]
    if mode in ("dense", "hybrid"):
        rankings += [[i for i, _ in dense_search(q, course, r["dense_k"], include_logistics)] for q in queries]
    if mode not in ("bm25", "dense", "hybrid"):
        raise ValueError(f"unknown mode {mode!r}")
    fused = rrf(rankings, r["rrf_k"])[:k]
    src = mode if mode != "hybrid" else "rrf"
    return [Hit(chunk_id=i, score=s, rank=n + 1, source=src) for n, (i, s) in enumerate(fused)]
