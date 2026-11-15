"""Orchestrator: guard -> router -> (content | logistics | navigation | clarify | off_topic)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC

from app.llm import QuotaError, collect_calls, new_trace, trace_event
from app.pipeline import gate, generate, guard, logistics, navigate, rerank, retrieve, rewrite, router, verify
from app.pipeline.router import pipeline_opt
from app.schemas import Answer, Hit, RouteDecision, Turn

OFF_TOPIC_REPLY = (
    "Я допомагаю лише з матеріалами курсів ПОК, АКС та ОС, тому з цим запитом допомогти не можу.\n\n"
    "Що я вмію:\n"
    "- пояснювати теми з лекцій і лабораторних зі посиланнями на слайди;\n"
    "- підказувати, у якій лекції та на якому слайді розглядається тема;\n"
    "- відповідати на організаційні питання з силабусів (оцінювання, дедлайни, інструменти).\n\n"
    "Спробуйте поставити запитання за темою курсів."
)
CLARIFY_REPLY = (
    "Не зовсім зрозуміло, що саме вас цікавить. Уточніть, будь ласка, тему або поняття "
    "і, якщо можна, курс (ПОК, АКС чи ОС)."
)
QUOTA_REPLIES = {
    "daily_free_limit": "Вичерпано денний ліміт безкоштовних запитів OpenRouter. "
    "Змініть API-ключ або зачекайте до скидання ліміту.",
    "rate_limited": "Безкоштовні моделі зараз перевантажені. Спробуйте ще раз за хвилину.",
    "no_credits": "Для цього запиту на ключі OpenRouter бракує коштів. Змініть API-ключ.",
    "auth": "API-ключ OpenRouter недійсний або відсутній. Змініть API-ключ.",
}
ERROR_REPLY = "Сталася технічна помилка під час обробки запитання. Спробуйте ще раз трохи згодом."


@contextmanager
def _stage(timings: dict[str, float], name: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = round(time.perf_counter() - t0, 3)
        trace_event(f"stage:{name}", seconds=timings[name])


def _hits_debug(hits: list[Hit]) -> list[dict]:
    return [{"chunk_id": h.chunk_id, "score": round(h.score, 4), "rank": h.rank} for h in hits]


def _badness(v) -> int:
    return len(v.unsupported_sentences) + len(v.bad_citations)


def _retrieve_and_gate(question: str, queries: list[str], course: str | None, timings: dict, dbg: dict):
    with _stage(timings, "retrieve"):
        cand = retrieve.run(queries, course)
    with _stage(timings, "rerank"):
        hits = rerank.run(queries[0], cand)
    with _stage(timings, "gate"):
        decision = gate.run(question, hits)
    trace_event("gate", **decision.model_dump(), course=course, hits=_hits_debug(hits))
    return hits, decision


def _content(question: str, history: list[Turn], rd: RouteDecision, timings: dict, dbg: dict) -> Answer:
    course = rd.course
    if rd.queries and pipeline_opt("merged_router", True):
        queries, dbg["rewrite_merged"] = rd.queries, True  # route+rewrite came from one LLM call
    else:
        with _stage(timings, "rewrite"):
            rw = rewrite.run(question, history, course)
        course, queries = rw.course, rw.queries
    dbg["queries"], dbg["course_filter"] = queries, course

    hits, decision = _retrieve_and_gate(question, queries, course, timings, dbg)
    if not decision.sufficient and course is not None:  # a wrong course hint must not cause a false abstain
        dbg["course_filter_dropped"] = True
        hits2, decision2 = _retrieve_and_gate(question, queries, None, timings, dbg)
        if decision2.sufficient:
            hits, decision = hits2, decision2
    dbg["hits"], dbg["gate"] = _hits_debug(hits), decision.model_dump()

    if not decision.sufficient:
        by_score = sorted(hits, key=lambda h: -h.score)
        return generate.abstain("content", generate.chunks_for(by_score), reason="gate")

    with _stage(timings, "generate"):
        ans = generate.run(question, history, hits)
    if ans.abstained:
        dbg["abstain_by"] = "generator"
        return ans
    chunks = generate.chunks_for(hits)
    if not pipeline_opt("verify", False):
        dbg["verify_skipped"] = True
        ans.debug["chunks_in_prompt"] = [c.chunk_id for c in chunks]
        return ans
    with _stage(timings, "verify"):
        ver = verify.run(ans, hits)
    dbg["verify"] = ver.model_dump()
    if not ver.supported:
        fix = ver.unsupported_sentences or [f"citation {t} does not support its sentence" for t in ver.bad_citations]
        with _stage(timings, "regenerate"):
            ans2 = generate.run(question, history, hits, fix=fix)
        if ans2.abstained:
            ver2 = None
        else:
            with _stage(timings, "verify2"):
                ver2 = verify.run(ans2, hits)
        dbg["verify_retry"] = ver2.model_dump() if ver2 else {"abstained": True}
        if ver2 is not None and _badness(ver2) < _badness(ver):
            ans, ver = ans2, ver2
            dbg["kept"] = "retry"
        else:
            dbg["kept"] = "first"
        dbg["verify_failed"] = not ver.supported
    ans.debug["chunks_in_prompt"] = [c.chunk_id for c in chunks]
    return ans


def run(question: str, history: list[Turn] | None = None) -> Answer:
    history = history or []
    tid = new_trace("q")
    timings: dict[str, float] = {}
    dbg: dict = {"timings": timings}
    calls = collect_calls()
    t_all = time.perf_counter()
    try:
        with _stage(timings, "guard"):
            g = guard.run(question)
        dbg["guard"] = g.model_dump(exclude={"text"})
        if not g.ok:
            ans = Answer(route="clarify", text=g.reply or CLARIFY_REPLY)
        else:
            q = g.text
            with _stage(timings, "router"):
                rd = router.run(q, history, g.flags)
            dbg["route"] = rd.model_dump()
            if rd.route == "off_topic":
                ans = Answer(route="off_topic", text=OFF_TOPIC_REPLY)
            elif rd.route == "clarify":
                ans = Answer(route="clarify", text=CLARIFY_REPLY)
            elif rd.route == "logistics":
                with _stage(timings, "logistics"):
                    ans = logistics.run(q, history, rd.course)
            elif rd.route == "navigation":
                with _stage(timings, "navigate"):
                    ans = navigate.run(q, rd.course)
            else:
                ans = _content(q, history, rd, timings, dbg)
    except QuotaError as e:
        trace_event("quota_error", kind=e.kind, model=e.model, error=e.message[:300])
        dbg["error_kind"] = "quota"
        dbg["quota"] = {
            "kind": e.kind,
            "model": e.model,
            "reset_at_iso": e.reset_at.astimezone(UTC).isoformat() if e.reset_at else None,
            "approximate": e.approximate,
        }
        ans = Answer(route="content", text=QUOTA_REPLIES.get(e.kind, ERROR_REPLY))
    except Exception as e:  # noqa: BLE001 — the UI must always get an Answer
        trace_event("pipeline_error", error=repr(e)[:500])
        dbg["error"] = repr(e)[:500]
        ans = Answer(route="content", text=ERROR_REPLY)
    dbg["llm_calls"] = calls
    timings["total"] = round(time.perf_counter() - t_all, 3)
    ans.trace_id = tid
    ans.debug = {**ans.debug, **dbg}
    trace_event("answer", route=ans.route, abstained=ans.abstained, n_citations=len(ans.citations))
    return ans
