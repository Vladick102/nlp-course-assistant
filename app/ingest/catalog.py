"""[DP] Per-document catalog for navigation questions. Writes data/index/catalog.json."""

from __future__ import annotations

import json

from app.config import path
from app.ingest.run import load_slides
from app.store import documents


def build() -> list[dict]:
    cat: list[dict] = []
    for doc in documents().values():
        try:
            slides = load_slides(doc.doc_id)
        except FileNotFoundError:
            continue
        seen: set[str] = set()
        titles: list[dict] = []
        for s in slides:
            if s.title and s.title not in seen:
                seen.add(s.title)
                titles.append({"title": s.title, "page": s.page_start})
        cat.append(
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "courses": doc.courses,
                "doc_type": doc.doc_type,
                "order": doc.order,
                "n_slides": len(slides),
                "slide_titles": titles,
                "summary": None,
            }
        )
    cat.sort(key=lambda d: (d["courses"], d["order"], d["doc_id"]))
    out = path("index")
    out.mkdir(parents=True, exist_ok=True)
    # keep summaries already filled by the LLM step
    prev = out / "catalog.json"
    if prev.exists():
        old = {d["doc_id"]: d.get("summary") for d in json.loads(prev.read_text(encoding="utf-8"))}
        for d in cat:
            d["summary"] = old.get(d["doc_id"])
    prev.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"catalog: {len(cat)} documents")
    return cat


if __name__ == "__main__":
    build()
