"""[DP] C2b — VLM figure descriptions → Slide.figure_description in slides.jsonl.

Usage: uv run python -m app.ingest.vlm [--limit N] [--only DOC_ID ...] [--workers 6] [--dry-run]

Every slide with `needs_vision` and no description is rendered (figures.page_png) and sent to the `vlm`
role together with its extracted text. Caching/retries live in app/llm.py, so reruns are free. Slides
the model judges decorative («ДЕКОРАТИВНЕ») keep `figure_description=None`, get `needs_vision=False` and a
`vision_reason` starting with DECORATIVE so they are not asked again. Failures are logged and skipped.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import cfg
from app.ingest import registry
from app.ingest.figures import page_png
from app.ingest.run import load_slides, save_slides
from app.llm import complete, load_prompt
from app.schemas import Document, Slide

DECORATIVE = "decorative (vlm)"
DECORATIVE_MARK = "ДЕКОРАТИВНЕ"
# Rough planning numbers for --dry-run only (tokens per call; USD per 1M tokens for a flash-class VLM).
EST_IN_TOKENS, EST_OUT_TOKENS = 1500, 250
EST_USD_PER_M_IN, EST_USD_PER_M_OUT = 0.30, 2.50


def pending(slides: list[Slide]) -> list[Slide]:
    return [
        s
        for s in slides
        if s.needs_vision and not s.figure_description and not (s.vision_reason or "").startswith(DECORATIVE)
    ]


def is_decorative(text: str) -> bool:
    return text.strip().strip("«»\"'`*. ").upper() == DECORATIVE_MARK


def _safe(t: str) -> str:
    return t.replace("{{", "{ {").replace("}}", "} }")


def describe(doc: Document, s: Slide) -> str:
    """One VLM call for one slide; returns the raw model text."""
    text = "\n".join([s.body_md, *s.footnotes]).strip() or "(тексту немає)"
    res = complete(
        load_prompt("vlm_figure"),
        role="vlm",
        images=[page_png(doc.pdf_path, s.page_end)],
        slide_text=_safe(text),
        title=_safe(s.title or "(без заголовка)"),
        doc_title=_safe(doc.title),
        max_tokens=700,
        step="vlm_figure",
    )
    return res.text.strip()


def apply(s: Slide, text: str) -> Slide:
    if is_decorative(text):
        return s.model_copy(
            update={
                "figure_description": None,
                "needs_vision": False,
                "vision_reason": f"{DECORATIVE}; was: {s.vision_reason}",
            }
        )
    return s.model_copy(update={"figure_description": text})


def estimate(n: int) -> float:
    return n * (EST_IN_TOKENS * EST_USD_PER_M_IN + EST_OUT_TOKENS * EST_USD_PER_M_OUT) / 1e6


def run(limit: int | None = None, only: list[str] | None = None, workers: int = 6, dry_run: bool = False) -> dict:
    docs = [d for d in registry.load() if not only or d.doc_id in only]
    todo: list[tuple[Document, list[Slide], Slide]] = []
    per_doc: dict[str, list[Slide]] = {}
    for d in docs:
        try:
            per_doc[d.doc_id] = load_slides(d.doc_id)
        except FileNotFoundError:
            print(f"skip {d.doc_id}: no slides.jsonl (run app.ingest.run)", file=sys.stderr)
            continue
        todo += [(d, per_doc[d.doc_id], s) for s in pending(per_doc[d.doc_id])]
    if limit is not None:
        todo = todo[:limit]
    total_flagged = sum(s.needs_vision for ss in per_doc.values() for s in ss)
    stats = {
        "flagged": total_flagged,
        "to_describe": len(todo),
        "est_usd": round(estimate(len(todo)), 3),
        "described": 0,
        "decorative": 0,
        "failed": 0,
    }
    print(
        f"{stats['flagged']} flagged slides, {stats['to_describe']} to describe "
        f"(model {cfg()['llm']['models']['vlm']}), est. cost ~${stats['est_usd']:.2f} (rough)"
    )
    if dry_run or not todo:
        return stats

    replaced: dict[tuple[str, int], Slide] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(describe, d, s): (d, s) for d, _, s in todo}
        for i, f in enumerate(as_completed(futs), 1):
            d, s = futs[f]
            try:
                new = apply(s, f.result())
            except Exception as e:  # noqa: BLE001 — never crash the batch
                stats["failed"] += 1
                print(f"[{i}/{len(todo)}] FAIL {s.slide_id}: {e!r}"[:300], file=sys.stderr)
                continue
            replaced[(d.doc_id, s.page_start)] = new
            stats["decorative" if new.figure_description is None else "described"] += 1
            print(f"[{i}/{len(todo)}] {s.slide_id} {'decorative' if new.figure_description is None else 'ok'}")

    for d in docs:
        if d.doc_id not in per_doc or not any(k[0] == d.doc_id for k in replaced):
            continue
        save_slides(d, [replaced.get((d.doc_id, s.page_start), s) for s in per_doc[d.doc_id]])
    print(stats)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.limit, a.only, a.workers, a.dry_run)


if __name__ == "__main__":
    main()
