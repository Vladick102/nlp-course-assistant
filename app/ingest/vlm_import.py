"""[DP] Import Haiku-agent figure descriptions (data/figure_descriptions/out/*.jsonl) into slides.jsonl.

Usage: uv run python -m app.ingest.vlm_import [DIR ...]

Lines are `{doc_id, page, description}`; `page` is matched against page_start <= page <= page_end of a slide.
The tracked files are the source of truth, so the import is idempotent and re-applied after every ingest.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from app.config import ROOT
from app.ingest import registry, vlm
from app.ingest.run import load_slides, save_slides
from app.schemas import Document, Slide

OUT_DIR = ROOT / "data" / "figure_descriptions" / "out"
REQUIRED = ("Тип:", "Висновок:")


def is_wellformed(text: str) -> bool:
    return vlm.is_decorative(text) or all(any(ln.strip().startswith(k) for ln in text.splitlines()) for k in REQUIRED)


def _read(dirs: list[Path], quiet: bool) -> tuple[int, list[dict]]:
    files = sorted(f for d in dirs for f in Path(d).glob("*.jsonl"))
    rows: list[dict] = []
    for f in files:
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
                rows.append({"doc_id": str(r["doc_id"]), "page": int(r["page"]), "description": str(r["description"])})
            except (ValueError, KeyError, TypeError):
                if not quiet:
                    print(f"warning: skipping unparsable line {f.name}:{i}", file=sys.stderr)
    return len(files), rows


def _overlay(s: Slide, text: str) -> Slide:
    if vlm.is_decorative(text):
        return s.model_copy(update={"figure_description": None, "needs_vision": False, "vision_reason": vlm.DECORATIVE})
    return s.model_copy(update={"figure_description": text.strip()})


def _covered(s: Slide) -> bool:
    return bool(s.figure_description) or (s.vision_reason or "").startswith(vlm.DECORATIVE)


def run(dirs: list[Path] | None = None, quiet: bool = False, docs: list[Document] | None = None) -> dict:
    nfiles, rows = _read(dirs or [OUT_DIR], quiet)
    stats: dict = {
        "files": nfiles,
        "lines": len(rows),
        "imported": 0,
        "decorative": 0,
        "malformed": 0,
        "unmatched": 0,
        "unmatched_examples": [],
    }
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r)
    known = {d.doc_id: d for d in (docs if docs is not None else registry.load())}
    cov: dict[str, list[int]] = {}
    for doc_id, d in known.items():
        try:
            slides = load_slides(doc_id)
        except FileNotFoundError:
            continue
        before = [s.model_copy() for s in slides]
        for r in by_doc.get(doc_id, []):
            idx = next((i for i, s in enumerate(slides) if s.page_start <= r["page"] <= s.page_end), None)
            if idx is None:
                stats["unmatched"] += 1
                if len(stats["unmatched_examples"]) < 5:
                    stats["unmatched_examples"].append(f"{doc_id}#{r['page']}")
                continue
            if not is_wellformed(r["description"]):
                stats["malformed"] += 1
            stats["decorative" if vlm.is_decorative(r["description"]) else "imported"] += 1
            slides[idx] = _overlay(slides[idx], r["description"])
        if slides != before:
            save_slides(d, slides)
        flagged = [s for s in slides if s.needs_vision or (s.vision_reason or "").startswith(vlm.DECORATIVE)]
        if flagged:
            cov[doc_id] = [sum(_covered(s) for s in flagged), len(flagged)]
    for doc_id, rs in by_doc.items():
        if doc_id not in known:
            stats["unmatched"] += len(rs)
            if len(stats["unmatched_examples"]) < 5:
                stats["unmatched_examples"].append(f"{doc_id}#{rs[0]['page']} (unknown doc)")
    done, total = sum(c[0] for c in cov.values()), sum(c[1] for c in cov.values())
    stats["coverage"] = {"done": done, "flagged": total, "ratio": round(done / total, 3) if total else 1.0}
    stats["coverage_per_doc"] = {k: f"{c[0]}/{c[1]}" for k, c in cov.items() if c[0]}
    if not quiet:
        print(
            f"vlm_import: {nfiles} files, {stats['lines']} lines: {stats['imported']} described, "
            f"{stats['decorative']} decorative, {stats['malformed']} malformed, {stats['unmatched']} unmatched "
            f"{stats['unmatched_examples']}; coverage {done}/{total} ({stats['coverage']['ratio']:.1%})"
        )
        for k, v in stats["coverage_per_doc"].items():
            print(f"  {k}: {v}")
    return stats


def main() -> None:
    run([Path(a) for a in sys.argv[1:]] or None)


if __name__ == "__main__":
    main()
