"""[EVAL] VLM model comparison for figure-slide descriptions (candidates on the draft figure gold set).

For each candidate (sequential): describe every gold item under override_models(vlm=candidate) with 4 workers.
Then, for each candidate and each judge (Sonnet and GPT-5.4, to control self-preference), judge the
descriptions. Metrics: entity recall, decorative accuracy, faithfulness and critical hallucinations per judge,
inter-judge Spearman rho, latency and cost from the JSONL trace, and projected cost for 1,073 slides.

Usage:
  uv run python scripts/compare_vlm.py --limit 3 --out /tmp/vlmcmp_smoke.json   # smoke run, budget check
  uv run python scripts/compare_vlm.py                                           # full run (30 items)
"""

from __future__ import annotations

import argparse
import contextvars
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import path  # noqa: E402
from app.ingest import registry  # noqa: E402
from app.ingest.vlm import describe, is_decorative  # noqa: E402
from app.llm import load_prompt, new_trace, override_models  # noqa: E402
from app.schemas import Slide  # noqa: E402
from eval.figure_eval import entity_recall, find_slide, judge  # noqa: E402
from eval.metrics import bootstrap_ci, spearman  # noqa: E402

GOLD = ROOT / "eval" / "data" / "review" / "figure_gold.jsonl"
CANDIDATES = ["google/gemini-3.6-flash", "anthropic/claude-sonnet-5.5", "openai/gpt-5.4-mini"]
JUDGES = {"sonnet": "anthropic/claude-sonnet-5.5", "gpt54": "openai/gpt-5.4"}
WORKERS = 4
N_FULL_SLIDES = 1073
BUDGET_USD = 5.0


def _short(model: str) -> str:
    return model.split("/", 1)[1]


def _nan_to_none(x: Any) -> Any:
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, dict):
        return {k: _nan_to_none(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_nan_to_none(v) for v in x]
    return x


def _describe_safe(doc: Any, slide: Slide | None) -> dict:
    if slide is None:
        return {"text": None, "error": "no slide for gold page"}
    try:
        return {"text": describe(doc, slide), "error": None}
    except Exception as e:  # noqa: BLE001 — record per-item errors, never abort the comparison
        return {"text": None, "error": repr(e)[:300]}


def _judge_safe(slide: Slide, pdf_path: str, text: str) -> dict:
    try:
        res = judge(slide.model_copy(update={"figure_description": text}), pdf_path)
        return {**res, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)[:300]}


def _run_pool(fn, argsets: list[tuple]) -> list[dict]:
    """Run fn over argsets in a thread pool; each task gets a copy of the current context
    (trace id + model overrides), so the trace and the override reach the worker threads."""
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(contextvars.copy_context().run, fn, *a) for a in argsets]
        return [f.result() for f in futs]


def _trace_lines(tids: set[str]) -> list[dict]:
    out: list[dict] = []
    for f in sorted(path("traces").glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            rec = json.loads(ln)
            if rec.get("trace_id") in tids:
                out.append(rec)
    return out


def _cost(rec: dict) -> float:
    c = (rec.get("usage") or {}).get("cost")
    return float(c) if c is not None else 0.0


def run(limit: int | None, out: Path) -> dict:
    gold = [json.loads(ln) for ln in GOLD.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # smoke run: evenly spaced items, so the sample mixes decorative and figure slides
    idx = np.linspace(0, len(gold) - 1, limit).round().astype(int) if limit else np.arange(len(gold))
    items = [gold[i] for i in idx]
    docs = {d.doc_id: d for d in registry.load()}
    slides = [find_slide(it["doc_id"], int(it["page"])) for it in items]
    print(f"{len(items)} gold items, {len(CANDIDATES)} candidates, judges={list(JUDGES)}")

    # ---- 1. descriptions, one trace per candidate
    gen: dict[str, dict] = {}  # model -> {"tid": str, "rows": [..]}
    for cand in CANDIDATES:
        tid = new_trace(f"vlmcmp-{_short(cand)}")
        with override_models(vlm=cand):
            rows = _run_pool(_describe_safe, [(docs[it["doc_id"]], sl) for it, sl in zip(items, slides, strict=True)])
        gen[cand] = {"tid": tid, "rows": rows}
        errs = sum(r["error"] is not None for r in rows)
        print(f"[describe] {cand}: {len(rows) - errs} ok, {errs} errors (trace {tid})")

    # ---- 2. judges, one trace per (candidate, judge)
    judged: dict[tuple[str, str], dict] = {}
    for cand in CANDIDATES:
        for jname, jmodel in JUDGES.items():
            tid = new_trace(f"vlmcmp-judge-{jname}-{_short(cand)}")
            todo = [
                (i, it)
                for i, (it, r) in enumerate(zip(items, gen[cand]["rows"], strict=True))
                if r["text"] and not is_decorative(r["text"]) and slides[i] is not None
            ]
            with override_models(judge=jmodel):
                res = _run_pool(
                    _judge_safe,
                    [(slides[i], docs[it["doc_id"]].pdf_path, gen[cand]["rows"][i]["text"]) for i, it in todo],
                )
            judged[(cand, jname)] = {"tid": tid, "by_item": {i: r for (i, _), r in zip(todo, res, strict=True)}}
            print(f"[judge:{jname}] {cand}: {len(todo)} judged (trace {tid})")

    # ---- 3. per-item rows
    item_rows = []
    for i, it in enumerate(items):
        row = {
            "doc_id": it["doc_id"],
            "page": it["page"],
            "visual_type": it["visual_type"],
            "decorative_gold": bool(it["decorative"]),
            "entities": it["entities"],
            "candidates": {},
        }
        for cand in CANDIDATES:
            r = gen[cand]["rows"][i]
            text = r["text"]
            dec_out = bool(text) and is_decorative(text)
            desc = None if (text is None or dec_out) else text
            c: dict[str, Any] = {
                "description": text,
                "error": r["error"],
                "output_decorative": dec_out,
                "decorative_correct": r["error"] is None and dec_out == row["decorative_gold"],
                "entity_recall": None if row["decorative_gold"] else entity_recall(it["entities"], desc),
                "judges": {},
            }
            for jname in JUDGES:
                jr = judged.get((cand, jname), {}).get("by_item", {}).get(i)
                if jr is not None:
                    c["judges"][jname] = jr
            row["candidates"][cand] = c
        item_rows.append(row)

    # ---- 4. summary per candidate
    summary: dict[str, Any] = {}
    all_tids = {v["tid"] for v in gen.values()} | {v["tid"] for v in judged.values()}
    lines = _trace_lines(all_tids)
    for cand in CANDIDATES:
        rows = [r["candidates"][cand] for r in item_rows]
        nondec = [r for r in item_rows if not r["decorative_gold"]]
        rec_vals = [r["candidates"][cand]["entity_recall"] for r in nondec]
        by_type: dict[str, dict] = {}
        for vt in sorted({r["visual_type"] for r in nondec}):
            vals = [r["candidates"][cand]["entity_recall"] for r in nondec if r["visual_type"] == vt]
            by_type[vt] = {"n": len(vals), "mean": float(np.mean(vals))}
        dec_hits = [r["candidates"][cand]["decorative_correct"] for r in item_rows]

        cand_lines = [x for x in lines if x.get("trace_id") == gen[cand]["tid"] and x.get("step") == "vlm_figure"]
        seen = sorted({x.get("model") for x in cand_lines})
        if seen != [cand]:
            raise RuntimeError(f"trace model mismatch for {cand}: {seen}")
        lat = [x["latency_s"] for x in cand_lines if not x.get("cached")]
        costs = [_cost(x) for x in cand_lines]
        cost_per = float(np.mean(costs)) if costs else float("nan")

        faith: dict[str, Any] = {}
        per_judge_scores: dict[str, dict[int, int]] = {}
        for jname in JUDGES:
            jr = [(i, r["judges"][jname]) for i, r in enumerate(rows) if jname in r["judges"]]
            ok = [(i, j) for i, j in jr if j.get("error") is None]
            scores = {i: j["faithfulness"] for i, j in ok}
            per_judge_scores[jname] = scores
            faith[jname] = {
                "faithfulness": bootstrap_ci([j["faithfulness"] for _, j in ok]) if ok else None,
                "critical_rate": float(np.mean([j["critical_hallucination"] for _, j in ok])) if ok else None,
                "n_judged": len(ok),
                "n_judge_errors": len(jr) - len(ok),
            }
        both = sorted(set(per_judge_scores["sonnet"]) & set(per_judge_scores["gpt54"]))
        rho = (
            spearman([per_judge_scores["sonnet"][i] for i in both], [per_judge_scores["gpt54"][i] for i in both])
            if len(both) >= 3
            else float("nan")
        )
        mean_of_judges = [(per_judge_scores["sonnet"][i] + per_judge_scores["gpt54"][i]) / 2 for i in both]
        vlm_spend = sum(_cost(x) for x in cand_lines if not x.get("cached"))
        judge_spend = sum(
            _cost(x)
            for k in judged
            if k[0] == cand
            for x in lines
            if x.get("trace_id") == judged[k]["tid"] and not x.get("cached")
        )
        summary[cand] = {
            "n_items": len(items),
            "n_errors": sum(r["candidates"][cand]["error"] is not None for r in item_rows),
            "entity_recall": bootstrap_ci(rec_vals),
            "entity_recall_n": len(rec_vals),
            "entity_recall_by_type": by_type,
            "decorative_accuracy": bootstrap_ci([float(h) for h in dec_hits]),
            "decorative_correct": int(sum(dec_hits)),
            "faithfulness": faith,
            "faithfulness_mean_of_judges": bootstrap_ci(mean_of_judges) if mean_of_judges else None,
            "judge_spearman_rho": rho,
            "judge_spearman_n": len(both),
            "latency_mean_s": float(np.mean(lat)) if lat else None,
            "latency_p95_s": float(np.percentile(lat, 95)) if lat else None,
            "latency_n_uncached": len(lat),
            "cost_per_description_usd": cost_per,
            "projected_1073_usd": cost_per * N_FULL_SLIDES,
            "spend_vlm_usd": vlm_spend,
            "spend_judges_usd": judge_spend,
            "models_seen_in_trace": seen,
            "same_family_judge": {
                "sonnet": cand.startswith("anthropic/"),
                "gpt54": cand.startswith("openai/"),
            },
        }

    total_spend = sum(s["spend_vlm_usd"] + s["spend_judges_usd"] for s in summary.values())
    result = {
        "date": str(date.today()),
        "gold_file": str(GOLD.relative_to(ROOT)),
        "gold_status": "DRAFT, not yet reviewed by a human",
        "n_items": len(items),
        "n_decorative_gold": sum(r["decorative_gold"] for r in item_rows),
        "candidates": CANDIDATES,
        "judges": JUDGES,
        "prompt_versions": {n: load_prompt(n).version for n in ("vlm_figure", "judge_figure")},
        "trace_ids": {c: gen[c]["tid"] for c in CANDIDATES}
        | {f"judge-{k[1]}-{_short(k[0])}": v["tid"] for k, v in judged.items()},
        "run_spend_usd": total_spend,
        "summary": summary,
        "items": item_rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_nan_to_none(result), ensure_ascii=False, indent=1), encoding="utf-8")
    print_summary(result)
    print(f"\nrun spend ${total_spend:.4f}; wrote {out}")
    if limit:
        projected = total_spend * len(gold) / len(items)
        print(f"projected spend for {len(gold)} items x 3 candidates: ${projected:.2f} (budget ${BUDGET_USD})")
        if projected > BUDGET_USD:
            print("STOP: projected spend exceeds budget", file=sys.stderr)
            sys.exit(2)
    return result


def _ci(t: Any, fmt: str = "{:.3f}") -> str:
    if not t or t[0] is None or (isinstance(t[0], float) and math.isnan(t[0])):
        return "n/a"
    return f"{fmt.format(t[0])} [{fmt.format(t[1])}, {fmt.format(t[2])}]"


def print_summary(res: dict) -> None:
    print(f"\n{'model':32} {'recall 95%CI':28} {'dec.acc':8} {'err':4} {'lat mean/p95 s':16} {'$/desc':9} {'$1073':8}")
    for cand, s in res["summary"].items():
        print(
            f"{cand:32} {_ci(s['entity_recall']):28} {s['decorative_correct']}/{s['n_items']:<6}"
            f"{s['n_errors']:<4} {s['latency_mean_s'] or 0:6.1f}/{s['latency_p95_s'] or 0:<8.1f}"
            f"{s['cost_per_description_usd']:<9.5f}{s['projected_1073_usd']:<8.1f}"
        )
        for jname in JUDGES:
            f = s["faithfulness"][jname]
            print(
                f"    judge {jname:6} faith {_ci(f['faithfulness'], '{:.2f}'):24} "
                f"crit {f['critical_rate']} n={f['n_judged']}"
            )
        print(f"    judge rho {s['judge_spearman_rho']} (n={s['judge_spearman_n']})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="N evenly spaced gold items (smoke run; enforces the budget)")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "eval" / f"vlm_comparison_{date.today()}.json")
    a = ap.parse_args()
    run(a.limit, a.out)


if __name__ == "__main__":
    main()
