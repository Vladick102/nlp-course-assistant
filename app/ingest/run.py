"""[DP] Offline ingestion: registry → parse → figure flags → data/parsed/<doc_id>/{slides.jsonl, <doc_id>.md}.

Usage: uv run python -m app.ingest.run [--only DOC_ID ...]
VLM descriptions are a separate, cached step: `python -m app.ingest.vlm`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from app.config import ROOT, cfg, path
from app.ingest import registry
from app.ingest.figures import flag_slides
from app.ingest.parser import parse_pdf, slide_to_md
from app.schemas import Document, Slide

LICENSE_RE = re.compile(r"^-?\s*(©.*|Creative Commons.*|CC BY-SA.*)$", re.M)


def strip_license(s: Slide) -> Slide:
    return s.model_copy(update={"body_md": LICENSE_RE.sub("", s.body_md).strip()})


def is_empty(s: Slide) -> bool:
    content = re.sub(r"\W+", "", s.body_md + "".join(s.footnotes))
    return len(content) < cfg()["ingest"]["min_chars"] and not s.needs_vision


def slides_file(doc_id: str):
    return path("parsed") / doc_id / "slides.jsonl"


def save_slides(doc: Document, slides: list[Slide]) -> None:
    d = path("parsed") / doc.doc_id
    d.mkdir(parents=True, exist_ok=True)
    with open(slides_file(doc.doc_id), "w", encoding="utf-8") as f:
        for s in slides:
            f.write(s.model_dump_json() + "\n")
    header = f"# {doc.title}\n\n`{doc.doc_id}` · курси: {', '.join(doc.courses)} · тип: {doc.doc_type}\n\n"
    (d / f"{doc.doc_id}.md").write_text(header + "\n\n".join(slide_to_md(s) for s in slides), encoding="utf-8")


def load_slides(doc_id: str) -> list[Slide]:
    with open(slides_file(doc_id), encoding="utf-8") as f:
        return [Slide(**json.loads(ln)) for ln in f]


def ingest_doc(doc: Document) -> dict:
    pdf = ROOT / doc.pdf_path
    slides = [strip_license(s) for s in parse_pdf(pdf, doc.doc_id)]
    slides = flag_slides(pdf, slides)
    kept = [s for s in slides if not is_empty(s)]
    # keep VLM descriptions from a previous run (they are expensive)
    if slides_file(doc.doc_id).exists():
        old = {s.page_start: s.figure_description for s in load_slides(doc.doc_id) if s.figure_description}
        kept = [s.model_copy(update={"figure_description": old.get(s.page_start)}) for s in kept]
    save_slides(doc, kept)
    return {
        "doc_id": doc.doc_id,
        "pages": doc.n_pages,
        "slides": len(kept),
        "merged_overlays": doc.n_pages - len(slides),
        "dropped_empty": len(slides) - len(kept),
        "needs_vision": sum(s.needs_vision for s in kept),
        "untitled": sum(s.title is None for s in kept),
        "with_links": sum(bool(s.urls) for s in kept),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    docs = registry.build()
    registry.save(docs)
    stats = []
    for d in docs:
        if a.only and d.doc_id not in a.only:
            continue
        st = ingest_doc(d)
        stats.append(st)
        print(json.dumps(st, ensure_ascii=False), file=sys.stderr)
    out = path("parsed") / "ingest_stats.json"
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    # tracked agent descriptions are the source of truth: re-apply them (incl. decorative marks)
    from app.ingest import vlm_import

    vlm_import.run(quiet=True)


if __name__ == "__main__":
    main()
