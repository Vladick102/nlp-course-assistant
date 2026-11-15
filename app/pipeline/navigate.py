"""Navigation ("which lecture covers X"): lexical match over catalog titles + retrieval hits per document."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app import store, text
from app.config import cfg
from app.llm import complete, load_prompt
from app.pipeline import retrieve
from app.pipeline.generate import abstain, build_answer
from app.pipeline.guard import esc
from app.schemas import Answer, Chunk

MAX_DOCS = 3
MAX_SLIDES = 3
SNIPPET_CHARS = 200
LIST_DOCS = 8  # when the question is a pure "list lectures" request, show this many documents


def _slides(entry: dict[str, Any]) -> list[tuple[int, str]]:
    """Normalise catalog slide titles to [(page, title)]; accepts list[str] or list[dict]."""
    raw = entry.get("slides") or entry.get("slide_titles") or []
    out: list[tuple[int, str]] = []
    for i, s in enumerate(raw, 1):
        if isinstance(s, dict):
            page = s.get("page_start") or s.get("page") or i
            title = s.get("title") or ""
        else:
            page, title = i, str(s)
        if title:
            out.append((int(page), str(title)))
    return out


def _overlap(q: set[str], s: str) -> int:
    return len(q & set(text.lemmas(s)))


def run(question: str, course: str | None) -> Answer:
    catalog = [
        e
        for e in store.catalog()
        if e.get("doc_type") != "logistics" and (course is None or course in (e.get("courses") or [course]))
    ]
    chunks = store.chunks()
    q = set(text.lemmas(question))

    doc_score: dict[str, float] = defaultdict(float)
    slide_pick: dict[str, list[tuple[float, int]]] = defaultdict(list)  # doc -> [(score, page)]
    for e in catalog:
        d = e["doc_id"]
        doc_score[d] += 2.0 * _overlap(q, f"{e.get('title', '')} {e.get('summary', '')}") / max(len(q), 1)
        for page, title in _slides(e):
            o = _overlap(q, title)
            if o:
                slide_pick[d].append((o / max(len(q), 1), page))
                doc_score[d] += o / max(len(q), 1)
    try:
        hits = retrieve.run([question], course, k=12)
    except Exception:  # noqa: BLE001 — catalog match alone can still answer
        hits = []
    by_id = {e["doc_id"]: e for e in catalog}
    for h in hits:
        c = chunks.get(h.chunk_id)
        if c and c.doc_id in by_id:
            doc_score[c.doc_id] += h.score
            if c.page_start is not None:
                slide_pick[c.doc_id].append((h.score, c.page_start))

    ranked = [d for d, s in sorted(doc_score.items(), key=lambda kv: -kv[1]) if s > 0][:MAX_DOCS]
    if not ranked and course is not None:  # "list the lectures of course X"
        ranked = [e["doc_id"] for e in sorted(catalog, key=lambda e: e.get("order", 999.0))][:LIST_DOCS]

    flat: list[Chunk] = []
    blocks: list[str] = []
    for d in ranked:
        e = by_id[d]
        titles = dict(_slides(e))
        pages = [p for _, p in sorted(slide_pick[d], key=lambda t: -t[0])]
        pages = list(dict.fromkeys(pages))[:MAX_SLIDES]
        names = "/".join(cfg()["courses"][c]["short"] for c in e.get("courses", []) if c in cfg()["courses"])
        lines = [f"Документ: {names} · {e.get('title', d)} (курс: {names}, №{e.get('order', '?')})"]
        cands = [chunks[f"{d}#{p}"] for p in pages if f"{d}#{p}" in chunks]
        if not cands and f"{d}#summary" in chunks:
            cands = [chunks[f"{d}#summary"]]
        for c in cands:
            flat.append(c)
            page = f"сл. {c.page_start}" if c.page_start is not None else "огляд"
            title = c.title or titles.get(c.page_start or -1, "")
            snippet = " ".join(c.text.split())[:SNIPPET_CHARS]
            lines.append(f"  [S{len(flat)}] {page} — {title}: {snippet}")
        blocks.append("\n".join(lines))
    if not flat:
        return abstain("navigation", [])
    res = complete(
        load_prompt("navigate"),
        "generator",
        step="navigate",
        max_tokens=800,
        question=esc(question),
        candidates=esc("\n".join(blocks)),
    )
    ans = build_answer("navigation", res.text, flat)
    ans.debug["nav_docs"] = ranked
    return ans
