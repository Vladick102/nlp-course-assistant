"""[EVAL] Retrieval ablation on a QA gold file (no LLM calls: the raw question is the query).

Usage: uv run python -m eval.retrieval_eval [--gold eval/data/qa_dev.jsonl] [--skip-rerank] [--limit N]

Counting rule (docs/gold_schema.md): a ranked chunk is a hit if it IS a gold id, if it is a window chunk covering the
page of a gold slide chunk, or if it is a slide chunk covered by a gold window chunk. Metrics: Recall@1/5/10 (any gold
hit in the top-k), MRR@10, nDCG@10, with percentile-bootstrap 95% CIs over items.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from app.config import ROOT, cfg
from app.pipeline import rerank, retrieve
from app.schemas import Chunk, Hit
from app.store import chunks
from eval.metrics import bootstrap_ci, hit_at_k, mrr_at_k, ndcg_at_k

DEFAULT_GOLD = ROOT / "eval" / "data" / "qa_dev.jsonl"
METRICS = ("R@1", "R@5", "R@10", "MRR@10", "nDCG@10")


def covers(a: Chunk, b: Chunk) -> bool:
    """True if chunk `a` (window) covers chunk `b` (slide) in the same document."""
    return (
        a.kind == "window"
        and b.kind != "window"
        and a.doc_id == b.doc_id
        and a.page_start is not None
        and b.page_start is not None
        and a.page_start <= b.page_start <= (a.page_end or a.page_start)
    )


def canonical(ranked: list[str], gold: list[str], cs: dict[str, Chunk]) -> tuple[list[str], set[str]]:
    """Map every ranked id that matches a gold chunk (exactly, window⊇slide or slide⊆window) to that gold id."""
    gold_in = [g for g in gold if g in cs]
    out = []
    for cid in ranked:
        c = cs[cid]
        m = next((g for g in gold_in if g == cid or covers(c, cs[g]) or covers(cs[g], c)), cid)
        out.append(m)
    return out, set(gold)


def item_metrics(ranked: list[str], gold: list[str], cs: dict[str, Chunk]) -> dict[str, float]:
    mapped, g = canonical(ranked, gold, cs)
    return {
        "R@1": hit_at_k(mapped, g, 1),
        "R@5": hit_at_k(mapped, g, 5),
        "R@10": hit_at_k(mapped, g, 10),
        "MRR@10": mrr_at_k(mapped, g, 10),
        "nDCG@10": ndcg_at_k(mapped, g, 10),
    }


def load_gold(p: Path, limit: int | None) -> list[dict]:
    items = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items[:limit] if limit else items


def retrieve_all(
    items: list[dict], mode: str, glossary: bool, k: int, use_course: bool
) -> tuple[list[list[Hit]], list[float]]:
    res, lat = [], []
    for it in items:
        t = time.perf_counter()
        res.append(
            retrieve.run([it["question"]], it["course"] if use_course else None, k=k, mode=mode, use_glossary=glossary)
        )
        lat.append(time.perf_counter() - t)
    return res, lat


def score_config(
    items: list[dict], hits: list[list[Hit]], lat: list[float], cs: dict[str, Chunk], extra: dict | None = None
) -> dict:
    per = [item_metrics([h.chunk_id for h in hs], it["gold_chunk_ids"], cs) for it, hs in zip(items, hits, strict=True)]

    def agg(idx: list[int]) -> dict:
        d = {"n": len(idx)}
        for m in METRICS:
            p, lo, hi = bootstrap_ci([per[i][m] for i in idx])
            d[m] = {"mean": p, "lo": lo, "hi": hi}
        return d

    groups: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        groups[f"type={it['type']}"].append(i)
        groups[f"lang={it['lang']}"].append(i)
    return {
        **(extra or {}),
        "overall": agg(list(range(len(items)))),
        "by_group": {g: agg(ix) for g, ix in sorted(groups.items())},
        "latency_s": float(np.mean(lat)),
        "per_item": [{"id": it["id"], **m} for it, m in zip(items, per, strict=True)],
    }


def fmt(d: dict, m: str) -> str:
    return f"{d[m]['mean']:.3f} [{d[m]['lo']:.2f}-{d[m]['hi']:.2f}]"


def markdown(report: dict) -> str:
    cfgs = report["configs"]
    n = report["n_items"]
    lines = [f"### Retrieval ablation — {report['gold']} (n={n})", ""]
    lines += ["| config | " + " | ".join(METRICS) + " | latency s/query |", "|---|" + "---|" * (len(METRICS) + 1)]
    for name, c in cfgs.items():
        lines.append(f"| {name} | " + " | ".join(fmt(c["overall"], m) for m in METRICS) + f" | {c['latency_s']:.2f} |")
    groups = sorted({g for c in cfgs.values() for g in c["by_group"]})
    lines += ["", "#### By question type / language (R@5 / nDCG@10, n in header)", ""]
    ns = {g: next(c["by_group"][g]["n"] for c in cfgs.values() if g in c["by_group"]) for g in groups}
    lines += ["| config | " + " | ".join(f"{g} (n={ns[g]})" for g in groups) + " |", "|---|" + "---|" * len(groups)]
    for name, c in cfgs.items():
        cells = [
            f"{c['by_group'][g]['R@5']['mean']:.2f} / {c['by_group'][g]['nDCG@10']['mean']:.2f}"
            if g in c["by_group"]
            else "-"
            for g in groups
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run(
    gold: Path,
    limit: int | None = None,
    skip_rerank: bool = False,
    settings: list[tuple[int, int]] | None = None,
    rerank_model: str | None = None,
    use_course: bool = True,
    rerank_glossary: bool = False,
) -> dict:
    items = load_gold(gold, limit)
    cs = chunks()
    k = cfg()["retrieval"]["fused_k"]
    missing = [g for it in items for g in it["gold_chunk_ids"] if g not in cs]
    if missing:
        print(f"warning: {len(missing)} gold chunk ids not in the index (e.g. {missing[:3]})")
    retrieve.run(["warm up"], None, k=3)  # load BM25 / dense / embedder before timing
    configs: dict[str, dict] = {}
    base: dict[tuple[str, bool], tuple[list[list[Hit]], list[float]]] = {}
    for name, mode, gl in [
        ("bm25", "bm25", False),
        ("dense", "dense", False),
        ("hybrid (RRF)", "hybrid", False),
        ("hybrid+glossary", "hybrid", True),
    ]:
        hits, lat = retrieve_all(items, mode, gl, k, use_course)
        base[(mode, gl)] = (hits, lat)
        configs[name] = score_config(items, hits, lat, cs, {"mode": mode, "glossary": gl})
        print(f"done {name}", flush=True)

    if not skip_rerank:
        hits0, lat0 = base[("hybrid", rerank_glossary)]
        rr_model = rerank_model or cfg()["retrieval"].get("rerank_model", rerank.DEFAULT_MODEL)
        best: tuple[float, tuple[int, int]] | None = None
        for cand, ml in settings or [(30, 512), (15, 384), (10, 256)]:
            out, lat = [], []
            for it, hs, l0 in zip(items, hits0, lat0, strict=True):
                t = time.perf_counter()
                out.append(rerank.run(it["question"], hs, k=k, candidates=cand, max_length=ml, model=rr_model))
                lat.append(l0 + time.perf_counter() - t)
            name = f"hybrid{'+glossary' if rerank_glossary else ''}+rerank({cand},{ml})"
            configs[name] = score_config(
                items, out, lat, cs, {"rerank": [cand, ml], "model": rr_model, "glossary": rerank_glossary}
            )
            print(f"done {name}", flush=True)
            sc = configs[name]["overall"]["nDCG@10"]["mean"]
            if best is None or sc > best[0]:
                best = (sc, (cand, ml))
        if best and not rerank_glossary:
            cand, ml = best[1]
            hits1, lat1 = base[("hybrid", True)]
            out, lat = [], []
            for it, hs, l0 in zip(items, hits1, lat1, strict=True):
                t = time.perf_counter()
                out.append(rerank.run(it["question"], hs, k=k, candidates=cand, max_length=ml, model=rr_model))
                lat.append(l0 + time.perf_counter() - t)
            name = f"hybrid+glossary+rerank({cand},{ml})"
            configs[name] = score_config(
                items, out, lat, cs, {"rerank": [cand, ml], "glossary": True, "model": rr_model}
            )
    return {
        "date": str(date.today()),
        "gold": str(gold.relative_to(ROOT)) if gold.is_relative_to(ROOT) else str(gold),
        "n_items": len(items),
        "course_filter": use_course,
        "embed_model": cfg()["retrieval"]["embed_model"],
        "configs": configs,
    }


def split_name(gold: Path) -> str:
    stem = gold.stem  # qa_dev -> dev; qa -> review
    return stem.split("_", 1)[1] if "_" in stem else "review"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--skip-rerank", action="store_true")
    ap.add_argument("--rerank-model")
    ap.add_argument("--rerank-settings", default="30:512,15:384,10:256", help="candidates:max_length,...")
    ap.add_argument("--no-course", action="store_true", help="do not filter by the item's course")
    ap.add_argument("--rerank-glossary", action="store_true", help="rerank on top of hybrid+glossary only")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    gold = a.gold if a.gold.is_absolute() else ROOT / a.gold
    settings = [tuple(map(int, s.split(":"))) for s in a.rerank_settings.split(",")]
    report = run(gold, a.limit, a.skip_rerank, settings, a.rerank_model, not a.no_course, a.rerank_glossary)  # type: ignore[arg-type]
    out = a.out or ROOT / "reports" / "eval" / f"retrieval_{date.today()}_{split_name(gold)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(markdown(report))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
