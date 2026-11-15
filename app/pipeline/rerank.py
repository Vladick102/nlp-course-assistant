"""[MOD] Cross-encoder reranker (default bge-reranker-v2-m3); scores are sigmoid in 0..1.

Config (retrieval.*): rerank_model, rerank_candidates (hits sent to the cross-encoder, default 30),
rerank_max_length (tokens per pair, default 512), use_reranker.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import torch

from app.config import cfg
from app.schemas import Hit
from app.store import chunks

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


@cache
def _model(name: str, max_length: int):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(name, device="cpu", max_length=max_length)


def run(
    query: str,
    hits: list[Hit],
    k: int | None = None,
    candidates: int | None = None,
    max_length: int | None = None,
    model: str | None = None,
) -> list[Hit]:
    """Rerank the first `candidates` hits; explicit arguments override config (used by the eval ablation)."""
    r = cfg()["retrieval"]
    k = k or r["final_k"]
    if not r["use_reranker"] or not hits:
        return hits[:k]
    candidates = candidates or r.get("rerank_candidates", 30)
    max_length = max_length or r.get("rerank_max_length", 512)
    model = model or r.get("rerank_model", DEFAULT_MODEL)
    hits = hits[:candidates]
    cs = chunks()
    # ~4 chars/token is a safe upper bound for mixed uk/en text; the tokenizer truncates the rest
    chars = max_length * 4
    pairs = [(query, cs[h.chunk_id].search_text[:chars]) for h in hits]
    ce = _model(model, max_length)
    logits = np.asarray(ce.predict(pairs, batch_size=8, activation_fn=torch.nn.Identity()), dtype=np.float64)
    probs = 1.0 / (1.0 + np.exp(-logits))
    order = np.argsort(-probs)[:k]
    return [
        Hit(chunk_id=hits[i].chunk_id, score=float(probs[i]), rank=n + 1, source="rerank") for n, i in enumerate(order)
    ]
