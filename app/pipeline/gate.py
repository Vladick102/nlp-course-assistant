"""Sufficiency gate: rerank-score threshold, with an LLM yes/no inside the borderline band."""

from __future__ import annotations

from app import store
from app.config import cfg
from app.llm import QuotaError, complete_json, load_prompt, trace_event
from app.pipeline.guard import esc
from app.schemas import GateDecision, Hit

LLM_PASSAGES = 4
PASSAGE_CHARS = 900


def run(question: str, hits: list[Hit]) -> GateDecision:
    g = cfg()["gate"]
    top = max((h.score for h in hits), default=0.0)
    if not hits:
        return GateDecision(sufficient=False, top_score=0.0, method="threshold", reason="no hits")
    thr = g["rerank_threshold"]
    band = g.get("borderline")
    if not band:
        return GateDecision(sufficient=top >= thr, top_score=top, method="threshold", reason=f"top {top:.3f} vs {thr}")
    lo, hi = band
    if top < lo:
        return GateDecision(sufficient=False, top_score=top, method="threshold", reason=f"top {top:.3f} < {lo}")
    if top > hi:
        return GateDecision(sufficient=True, top_score=top, method="threshold", reason=f"top {top:.3f} > {hi}")

    chunks = store.chunks()
    best = sorted(hits, key=lambda h: -h.score)[:LLM_PASSAGES]
    passages = "\n\n".join(
        f"[S{i}] {chunks[h.chunk_id].breadcrumb}\n{chunks[h.chunk_id].text[:PASSAGE_CHARS]}"
        for i, h in enumerate(best, 1)
        if h.chunk_id in chunks
    )
    try:
        data, _ = complete_json(
            load_prompt("gate"), "fast", step="gate", question=esc(question), passages=esc(passages)
        )
        ok = data["sufficient"]
        if not isinstance(ok, bool):
            raise ValueError("sufficient is not bool")
        return GateDecision(sufficient=ok, top_score=top, method="llm", reason=str(data.get("reason", ""))[:300])
    except QuotaError:
        raise  # quota must reach the UI banner / eval resume logic, never be hidden
    except Exception as e:  # noqa: BLE001 — LLM failed: fall back to the plain threshold
        trace_event("gate_fallback", error=repr(e)[:300])
        return GateDecision(
            sufficient=top >= thr, top_score=top, method="threshold", reason=f"llm failed, top {top:.3f} vs {thr}"
        )
