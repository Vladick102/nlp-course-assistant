"""[DP] Slides -> Chunks (per slide + windows over same-title runs). Writes data/index/chunks.jsonl."""

from __future__ import annotations

import re

from app.config import cfg, path
from app.ingest.run import load_slides
from app.schemas import Chunk, Document, Slide

FIG_PREFIX = "[Опис зображення, згенеровано моделлю]"
CONT_RE = re.compile(
    r"\s*[\(\[]\s*(?:\d+\s*(?:/|з|of)?\s*\d*|продовження|cont\.?)\s*[\)\]]\s*$|\s*\(\s*продовження\s*\)$", re.I
)


def norm_title(t: str | None) -> str | None:
    if not t:
        return None
    return CONT_RE.sub("", t).strip().lower() or None


def breadcrumb(doc: Document, section: str | None, title: str | None) -> str:
    courses = cfg()["courses"]
    parts = [" ".join(courses[c]["short"] for c in doc.courses if c in courses), doc.title, section, title]
    return " › ".join(p for p in parts if p)


def slide_text(s: Slide) -> str:
    parts = [s.body_md.strip()]
    if s.footnotes:
        parts.append("Примітка: " + " ".join(s.footnotes))
    if s.figure_description:
        parts.append(f"{FIG_PREFIX} {s.figure_description}")
    return "\n\n".join(p for p in parts if p)


def _chunk(doc: Document, s: Slide, kind: str) -> Chunk:
    bc = breadcrumb(doc, s.section, s.title)
    text = slide_text(s)
    return Chunk(
        chunk_id=f"{doc.doc_id}#{s.page_start}",
        doc_id=doc.doc_id,
        courses=doc.courses,
        doc_type=doc.doc_type,
        kind=kind,
        page_start=s.page_start,
        page_end=s.page_end,
        title=s.title,
        breadcrumb=bc,
        text=text,
        search_text=f"{bc}\n{text}",
        urls=s.urls,
    )


def doc_chunks(doc: Document, slides: list[Slide]) -> list[Chunk]:
    logistics = doc.doc_type == "logistics"
    out = [_chunk(doc, s, "logistics" if logistics else "slide") for s in slides]
    if logistics:
        return out
    i = 0
    while i < len(slides):
        key = norm_title(slides[i].title)
        j = i + 1
        while key and j < len(slides) and norm_title(slides[j].title) == key:
            j += 1
        if j - i > 1:
            run = slides[i:j]
            first = run[0]
            bc = breadcrumb(doc, first.section, CONT_RE.sub("", first.title or "").strip())
            text = "\n\n".join(slide_text(s) for s in run)
            out.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#w{first.page_start}",
                    doc_id=doc.doc_id,
                    courses=doc.courses,
                    doc_type=doc.doc_type,
                    kind="window",
                    page_start=first.page_start,
                    page_end=run[-1].page_end,
                    title=CONT_RE.sub("", first.title or "").strip(),
                    breadcrumb=bc,
                    text=text,
                    search_text=f"{bc}\n{text}",
                    urls=sorted({u for s in run for u in s.urls}),
                )
            )
        i = j
    return out


def build() -> list[Chunk]:
    from app.store import documents

    chunks: list[Chunk] = []
    for doc in documents().values():
        try:
            slides = load_slides(doc.doc_id)
        except FileNotFoundError:
            continue
        chunks += doc_chunks(doc, slides)
    out = path("index")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")
    kinds = {k: sum(c.kind == k for c in chunks) for k in ("slide", "window", "logistics")}
    print(f"chunks: {len(chunks)} {kinds}")
    return chunks


if __name__ == "__main__":
    build()
