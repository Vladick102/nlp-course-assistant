"""Logistics answerer: only doc_type=="logistics" chunks (syllabi + requirements), always cited."""

from __future__ import annotations

from app import store, text
from app.llm import complete, load_prompt
from app.pipeline import retrieve
from app.pipeline.generate import abstain, build_answer, format_passages
from app.pipeline.guard import esc
from app.pipeline.router import format_history
from app.schemas import Answer, Chunk, Turn

MAX_PASSAGES = 8
PASSAGE_CHARS = 3000


def _is_logistics(c: Chunk) -> bool:
    return c.kind == "logistics" and c.doc_type == "logistics"


def select_chunks(question: str, course: str | None) -> list[Chunk]:
    pool = {cid: c for cid, c in store.chunks().items() if _is_logistics(c) and (course is None or course in c.courses)}
    picked: list[Chunk] = []
    try:
        for h in retrieve.run([question], course, k=MAX_PASSAGES * 2, include_logistics=True):
            if h.chunk_id in pool and pool[h.chunk_id] not in picked:
                picked.append(pool[h.chunk_id])
    except Exception:  # noqa: BLE001 — retrieval trouble: lexical fallback below still works
        pass
    if len(picked) < MAX_PASSAGES:  # top up with lexical overlap so a weak BM25 run never starves the answer
        q = set(text.lemmas(question))
        rest = sorted(
            (c for c in pool.values() if c not in picked),
            key=lambda c: -len(q & set(text.lemmas(c.search_text))),
        )
        picked += rest[: MAX_PASSAGES - len(picked)]
    return picked[:MAX_PASSAGES]


def run(question: str, history: list[Turn], course: str | None) -> Answer:
    chunks = [c.model_copy(update={"text": c.text[:PASSAGE_CHARS]}) for c in select_chunks(question, course)]
    if not chunks:
        return abstain("logistics", [])
    res = complete(
        load_prompt("logistics"),
        "generator",
        step="logistics",
        max_tokens=1200,
        question=esc(question),
        chat=format_history(history),
        passages=format_passages(chunks, with_doc=True),
    )
    ans = build_answer("logistics", res.text, chunks)
    ans.debug["logistics_chunks"] = [c.chunk_id for c in chunks]
    return ans
