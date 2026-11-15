"""Standalone search queries (UA + EN terms) and a course hint from the chat history."""

from __future__ import annotations

from app.config import cfg
from app.llm import QuotaError, complete_json, load_prompt, trace_event
from app.pipeline.guard import esc
from app.pipeline.router import format_history
from app.schemas import Rewrite, Turn

MAX_QUERIES = 3


def run(question: str, history: list[Turn], course: str | None = None) -> Rewrite:
    try:
        data, _ = complete_json(
            load_prompt("rewrite"),
            "fast",
            step="rewrite",
            question=esc(question),
            chat=format_history(history),
        )
        raw = data.get("queries") if isinstance(data, dict) else None
        queries: list[str] = []
        for q in raw or []:
            q = str(q).strip()
            if q and q not in queries:
                queries.append(q)
        found = data.get("course") if isinstance(data, dict) else None
    except QuotaError:
        raise
    except Exception as e:  # noqa: BLE001 — fall back to the raw question
        trace_event("rewrite_fallback", error=repr(e)[:300])
        queries, found = [], None
    if not queries:
        queries = [question]
    out_course = found if found in cfg()["courses"] else course
    return Rewrite(queries=queries[:MAX_QUERIES], course=out_course)
