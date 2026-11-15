"""Grounded answer generation with [S1]..[Sk] citation tags, plus helpers shared by logistics/navigate."""

from __future__ import annotations

import re

from app import store
from app.config import cfg
from app.llm import complete, load_prompt
from app.pipeline.guard import esc
from app.pipeline.router import format_history
from app.schemas import Answer, Chunk, Citation, Hit, Route, Turn

ABSTAIN_TEXT = "У матеріалах курсу цього немає."
POINTERS = 3
FIX_BLOCK = (
    "\nCORRECTION: a fact-checker found these sentences of your previous draft unsupported by the passages. "
    "Remove them or rewrite them so that they are fully supported:\n{sentences}\n"
)

_ABSTAIN_RE = re.compile(
    r"у\s+(?:наданих\s+|цих\s+)?матеріалах(?:\s+курсу)?\s+(?:цього|цієї|такої\s+\w+|відповіді)?\s*(?:немає|нема)"
)
_NUM = r"S?\s*(\d+)"
_GROUP = re.compile(r"\[\s*(S\s*\d+(?:\s*(?:[,;]|[-–—])\s*S?\s*\d+)*)\s*\]", re.IGNORECASE)
_PART = re.compile(rf"{_NUM}(?:\s*[-–—]\s*{_NUM})?", re.IGNORECASE)


def _expand(inner: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"[,;]", inner):
        m = _PART.search(part)
        if not m:
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        nums.extend(range(a, min(b, a + 20) + 1) if b >= a else [a])
    return nums


def course_label(chunk: Chunk) -> str:
    courses = cfg()["courses"]
    return "/".join(courses[c]["short"] for c in chunk.courses if c in courses)


def citation_for(chunk: Chunk, tag: str = "") -> Citation:
    docs = store.documents()
    doc = docs.get(chunk.doc_id)
    title = doc.title if doc else (chunk.title or chunk.doc_id)
    parts = [course_label(chunk), title]
    if chunk.page_start is not None:
        end = chunk.page_end
        pages = str(chunk.page_start) if end in (None, chunk.page_start) else f"{chunk.page_start}–{end}"
        parts.append(f"сл. {pages}")
    return Citation(
        tag=tag,
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        label=" · ".join(p for p in parts if p),
        title=chunk.title,
        urls=list(chunk.urls),
    )


def chunks_for(hits: list[Hit]) -> list[Chunk]:
    all_chunks = store.chunks()
    return [all_chunks[h.chunk_id] for h in hits if h.chunk_id in all_chunks]


def format_passages(chunks: list[Chunk], with_doc: bool = False) -> str:
    out = []
    for i, c in enumerate(chunks, 1):
        doc = f" (document: {c.doc_id})" if with_doc else ""
        urls = f"\nURLs: {', '.join(c.urls)}" if c.urls else ""
        out.append(f"[S{i}] {c.breadcrumb}{doc}\n{c.text}{urls}")
    return esc("\n\n".join(out))


def parse_citations(text: str, chunks: list[Chunk]) -> tuple[str, list[Citation], list[str]]:
    """Normalise tags to `[S1][S3]`, drop unknown ones. Returns (clean_text, citations, invalid_tags)."""
    cited: list[int] = []
    invalid: list[str] = []

    def repl(m: re.Match[str]) -> str:
        keep: list[int] = []
        for n in _expand(m.group(1)):
            if 1 <= n <= len(chunks):
                if n not in keep:
                    keep.append(n)
                if n not in cited:
                    cited.append(n)
            elif f"S{n}" not in invalid:
                invalid.append(f"S{n}")
        return "".join(f"[S{n}]" for n in keep)

    clean = _GROUP.sub(repl, text)
    clean = re.sub(r"[ \t]+([.,;:!?])", r"\1", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean, [citation_for(chunks[n - 1], f"S{n}") for n in cited], invalid


def is_abstain(text: str) -> bool:
    plain = _GROUP.sub("", text).strip().casefold()
    return bool(_ABSTAIN_RE.match(plain))


def abstain(route: Route, pointers: list[Chunk], **debug: object) -> Answer:
    """Standard «not in the materials» answer with the closest slides as pointers."""
    cites: list[Citation] = []
    for c in pointers:
        cit = citation_for(c)
        if cit.label not in [x.label for x in cites]:
            cites.append(cit)
        if len(cites) >= POINTERS:
            break
    text = ABSTAIN_TEXT
    if cites:
        lines = "\n".join(f"- {c.label}" + (f" — {c.title}" if c.title else "") for c in cites)
        text += f"\n\nНайближчі за темою місця в матеріалах (відповіді там може й не бути):\n{lines}"
    return Answer(route=route, text=text, citations=cites, abstained=True, debug=dict(debug))


def build_answer(route: Route, raw: str, chunks: list[Chunk]) -> Answer:
    """Turn raw model output into an Answer (citations, invalid tags, abstain detection)."""
    if is_abstain(raw):
        return abstain(route, chunks, raw=raw, tag_map={})
    text, cites, invalid = parse_citations(raw, chunks)
    tag_map = {f"S{i}": c.chunk_id for i, c in enumerate(chunks, 1)}
    return Answer(
        route=route,
        text=text,
        citations=cites,
        invalid_citations=invalid,
        debug={"raw": raw, "tag_map": tag_map},
    )


def run(question: str, history: list[Turn], hits: list[Hit], fix: list[str] | None = None) -> Answer:
    chunks = chunks_for(hits)
    if not chunks:
        return abstain("content", [])
    fix_block = FIX_BLOCK.format(sentences="\n".join(f"- {s}" for s in fix)) if fix else ""
    res = complete(
        load_prompt("answer"),
        "generator",
        step="generate",
        max_tokens=1500,
        question=esc(question),
        chat=format_history(history),
        passages=format_passages(chunks),
        fix=esc(fix_block),
    )
    return build_answer("content", res.text, chunks)
