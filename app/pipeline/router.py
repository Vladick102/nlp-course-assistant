"""LLM router: content / logistics / navigation / clarify / off_topic. Falls back to content on any failure."""

from __future__ import annotations

from app.config import cfg
from app.llm import QuotaError, complete_json, load_prompt, trace_event
from app.pipeline.guard import esc
from app.schemas import RouteDecision, Turn

_MAX_TURN_CHARS = 500


def format_history(history: list[Turn]) -> str:
    """Last `chat.history_turns` turns (user+assistant pairs) as plain text for prompts."""
    n = cfg()["chat"]["history_turns"] * 2
    recent = history[-n:] if n > 0 else []
    if not recent:
        return "(порожньо)"
    return esc("\n".join(f"{t.role}: {t.content[:_MAX_TURN_CHARS]}" for t in recent))


def pipeline_opt(name: str, default: bool) -> bool:
    """Boolean flag from config `pipeline:` section (absent => default)."""
    return bool((cfg().get("pipeline") or {}).get(name, default))


def _clean_queries(raw: object, limit: int = 3) -> list[str]:
    out: list[str] = []
    for q in raw if isinstance(raw, list) else []:
        q = str(q).strip()
        if q and q not in out:
            out.append(q)
    return out[:limit]


def run(question: str, history: list[Turn], flags: list[str] | None = None) -> RouteDecision:
    try:
        merged = pipeline_opt("merged_router", True)
        data, _ = complete_json(
            load_prompt("route_rewrite" if merged else "router"),
            "fast",
            step="router",
            question=esc(question),
            chat=format_history(history),
            flags=", ".join(flags or []) or "none",
        )
        if isinstance(data, dict) and data.get("course") in ("null", "", "none"):
            data["course"] = None
        if isinstance(data, dict):
            data["queries"] = _clean_queries(data.get("queries")) if merged else []
        return RouteDecision.model_validate(data)
    except QuotaError:
        raise
    except Exception as e:  # noqa: BLE001 — any LLM/parse/validation failure degrades to content
        trace_event("router_fallback", error=repr(e)[:300])
        return RouteDecision(route="content", confidence=0.0, reason=f"router failed: {type(e).__name__}")
