"""[EVAL] C2 figure-description evaluation (needs the VLM run and, for the judge, an API key).

Gold items (eval/data/figure_gold.jsonl, or --gold PATH): {doc_id, page, entities: [str], takeaway: str}
Metrics:
  * entity recall: share of gold entities found (case-insensitive substring, else fuzzy window match
    >= 0.85) in Slide.figure_description,
  * LLM judge (role "judge", prompts/judge_figure.md, sees the page image + description):
    faithfulness 1-5 (mean with bootstrap CI) and critical-hallucination rate.
Items whose slide has no description count as recall 0 and are reported as `missing_description`.

Usage: uv run python -m eval.figure_eval [--gold PATH] [--no-judge] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from app.config import ROOT
from app.ingest import registry
from app.ingest.figures import page_png
from app.ingest.run import load_slides
from app.llm import complete_json, load_prompt
from app.schemas import Slide
from eval.metrics import bootstrap_ci

DEFAULT_GOLD = ROOT / "eval" / "data" / "figure_gold.jsonl"
FUZZY = 0.85


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.casefold())).strip()


def entity_found(entity: str, description: str) -> bool:
    e, d = _norm(entity), _norm(description)
    if not e:
        return False
    if e in d:
        return True
    ew, dw = e.split(), d.split()
    n = len(ew)
    return any(
        SequenceMatcher(None, e, " ".join(dw[i : i + n])).ratio() >= FUZZY for i in range(max(len(dw) - n + 1, 0))
    )


def entity_recall(entities: list[str], description: str | None) -> float:
    if not entities:
        return 1.0
    if not description:
        return 0.0
    return sum(entity_found(e, description) for e in entities) / len(entities)


def find_slide(doc_id: str, page: int) -> Slide | None:
    return next((s for s in load_slides(doc_id) if s.page_start <= page <= s.page_end), None)


def judge(slide: Slide, pdf_path: str) -> dict:
    """One judge call → {faithfulness: int 1..5, critical_hallucination: bool, reason: str}."""
    out, _ = complete_json(
        load_prompt("judge_figure"),
        role="judge",
        images=[page_png(pdf_path, slide.page_end)],
        slide_text=(slide.body_md or "(тексту немає)").replace("{{", "{ {"),
        description=(slide.figure_description or "").replace("{{", "{ {"),
        max_tokens=400,
        step="judge_figure",
    )
    f = max(1, min(5, int(out["faithfulness"])))
    return {
        "faithfulness": f,
        "critical_hallucination": bool(out["critical_hallucination"]),
        "reason": str(out.get("reason", "")),
    }


def evaluate(items: list[dict], use_judge: bool = True) -> dict:
    docs = {d.doc_id: d for d in registry.load()}
    rows = []
    for it in items:
        s = find_slide(it["doc_id"], int(it["page"]))
        desc = s.figure_description if s else None
        row = {
            "doc_id": it["doc_id"],
            "page": it["page"],
            "entity_recall": entity_recall(it["entities"], desc),
            "missing_description": not desc,
        }
        if use_judge and s and desc:
            try:
                row |= judge(s, docs[it["doc_id"]].pdf_path)
            except Exception as e:  # noqa: BLE001 — one failed call must not sink the evaluation
                row["judge_error"] = repr(e)[:200]
        rows.append(row)
    return {"n": len(rows), **summarize(rows), "items": rows}


def summarize(rows: list[dict]) -> dict:
    rec = [r["entity_recall"] for r in rows]
    judged = [r for r in rows if "faithfulness" in r]
    out: dict = {
        "entity_recall": bootstrap_ci(rec) if rec else None,
        "missing_description": sum(r["missing_description"] for r in rows),
        "n_judged": len(judged),
    }
    if judged:
        out["faithfulness"] = bootstrap_ci([r["faithfulness"] for r in judged])
        out["critical_hallucination_rate"] = sum(r["critical_hallucination"] for r in judged) / len(judged)
    return out


def markdown(res: dict) -> str:
    def ci(t: tuple | list | None) -> str:
        return "n/a" if not t else f"{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]"

    lines = [
        f"### Figure descriptions (n={res['n']}, judged={res['n_judged']})",
        "",
        "| metric | value (95% CI) |",
        "|---|---|",
        f"| entity recall | {ci(res['entity_recall'])} |",
        f"| faithfulness 1-5 | {ci(res.get('faithfulness'))} |",
        f"| critical hallucination rate | {res.get('critical_hallucination_rate', 'n/a')} |",
        f"| items without description | {res['missing_description']} |",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if not a.gold.exists():
        raise SystemExit(f"gold file {a.gold} not found")
    items = [json.loads(ln) for ln in a.gold.read_text(encoding="utf-8").splitlines() if ln.strip()]
    res = {"date": str(date.today()), "gold_file": str(a.gold), **evaluate(items, not a.no_judge)}
    out = a.out or ROOT / "reports" / "eval" / f"figure_{date.today()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(markdown(res))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
