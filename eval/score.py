"""[EVAL] Scoring: turns run records (+ judge judgments) into per-component metrics. No LLM calls.

Usage:
  uv run python -m eval.score --component answer [--run RUN_ID] [--split dev] [--write]
  uv run python -m eval.score --component answer --run RUN_ID --check-judgments   # validate judgments_*.jsonl
Metric values are floats or {"value", "lo", "hi", "n"} (95% bootstrap CI over items).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path

import numpy as np

from eval import metrics as M
from eval import runs
from eval.runs import RunStore, read_jsonl

ROUTES = ["content", "logistics", "navigation", "clarify", "off_topic"]
IN_DOMAIN = {"content", "logistics", "navigation"}
JUDGED_ROUTES = {"content", "logistics", "navigation"}
FIG_DIR = runs.EVAL_DIR / "figures"
TRUE = {"y", "yes", "1", "true", "t", "так"}
FALSE = {"n", "no", "0", "false", "f", "ні"}


# ------------------------------------------------------------------ helpers
def rate(values: list[float], n_boot: int = 1000) -> dict:
    """Mean of 0/1 (or float) per-item values with a bootstrap CI."""
    if not values:
        return {"value": None, "lo": None, "hi": None, "n": 0}
    v, lo, hi = M.bootstrap_ci(values, n_boot=n_boot)
    return {"value": v, "lo": lo, "hi": hi, "n": len(values)}


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def latency_stats(values: list[float]) -> dict:
    return {
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "mean": float(np.mean(values)) if values else None,
    }


def clean(o):
    """JSON-safe copy: NaN/inf -> None, numpy -> python."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, np.generic):
        return clean(o.item())
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def models_served(recs: list[dict]) -> dict[str, int]:
    c: Counter = Counter()
    for r in recs:
        for call in r.get("llm_calls", []):
            c[call.get("model", "?")] += 1
    return dict(c)


def call_stats(recs: list[dict]) -> dict:
    n = [len(r.get("llm_calls", [])) for r in recs]
    live = [sum(not c.get("cached") for c in r.get("llm_calls", [])) for r in recs]
    return {
        "calls_per_item": float(np.mean(n)) if n else None,
        "live_calls_per_item": float(np.mean(live)) if live else None,
        "total_calls": int(sum(n)),
        "total_live_calls": int(sum(live)),
        "models_served": models_served(recs),
    }


# ------------------------------------------------------------------ chunk equivalence (slide <-> window)
def _parse_cid(cid: str) -> tuple[str, int | None]:
    doc, _, tail = cid.partition("#")
    m = re.fullmatch(r"w?(\d+)", tail)
    return doc, int(m.group(1)) if m else None


def default_span(cid: str) -> tuple[str, int, int] | None:
    """(doc_id, first_page, last_page) of a chunk id; uses the chunk store when available."""
    try:
        from app import store

        c = store.chunks().get(cid)
        if c is not None and c.page_start is not None:
            return c.doc_id, c.page_start, c.page_end or c.page_start
    except Exception:  # noqa: BLE001 — index not built / unit tests
        pass
    doc, p = _parse_cid(cid)
    return (doc, p, p) if p is not None else None


def chunk_match(cited: str, gold: str, span: Callable[[str], tuple[str, int, int] | None] = default_span) -> bool:
    """True if the cited chunk is the gold chunk or overlaps it (same doc, overlapping page range: window vs slide)."""
    if cited == gold:
        return True
    a, b = span(cited), span(gold)
    return bool(a and b and a[0] == b[0] and a[1] <= b[2] and b[1] <= a[2])


def cites_gold(cited_ids: list[str], gold_ids: list[str], span=default_span) -> bool:
    return any(chunk_match(c, g, span) for c in cited_ids for g in gold_ids)


# ------------------------------------------------------------------ router
def router_metrics(y_true: list[str], y_pred: list[str], labels: list[str] | None = None) -> dict:
    labels = labels or ROUTES
    prf = M.per_class_prf(y_true, y_pred, labels)
    in_dom = [(t, p) for t, p in zip(y_true, y_pred, strict=True) if t in IN_DOMAIN]
    fr = [float(p == "off_topic") for _, p in in_dom]
    return {
        "n": len(y_true),
        "accuracy": rate([float(t == p) for t, p in zip(y_true, y_pred, strict=True)]),
        "macro_f1": prf["macro_f1"],
        "per_class": {lab: prf[lab] for lab in labels},
        "confusion": {"labels": labels, "matrix": M.confusion(y_true, y_pred, labels).tolist()},
        "false_reject_rate": rate(fr),
    }


def router_baseline_preds(train: list[dict], test: list[dict]) -> list[str] | None:
    """TF-IDF (word + char n-grams) + logistic regression trained on `train`, predictions for `test`."""
    if len({r["gold_route"] for r in train}) < 2 or not test:
        return None
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline, make_union

    feats = make_union(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
    )
    clf = make_pipeline(feats, LogisticRegression(max_iter=2000, C=10.0))
    clf.fit([r["question"] for r in train], [r["gold_route"] for r in train])
    return [str(p) for p in clf.predict([r["question"] for r in test])]


def half_split(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic halves by sorted id: (train = even positions, held-out = odd positions)."""
    s = sorted(recs, key=lambda r: r["id"])
    return s[0::2], s[1::2]


def score_router(recs: list[dict], split: str = "dev", train_items: list[dict] | None = None) -> dict:
    y_t, y_p = [r["gold_route"] for r in recs], [r["route"] for r in recs]
    out = router_metrics(y_t, y_p)
    out["latency_s"] = latency_stats([r["latency_s"] for r in recs if "latency_s" in r])
    out.update(call_stats(recs))
    out["hard_accuracy"] = rate([float(r["route"] == r["gold_route"]) for r in recs if r.get("hard")])
    if train_items:  # explicit training items (preset: the router items not sampled; test: half of dev gold)
        train, held = train_items, recs
    elif split == "dev":
        train, held = half_split(recs)
    else:
        train, held = [], recs
    base = router_baseline_preds(train, held) if train else None
    if base is not None:
        yt = [r["gold_route"] for r in held]
        llm_held = [r["route"] for r in held]
        out["baseline"] = {
            "kind": "tfidf+logreg",
            "train_n": len(train),
            "eval_n": len(held),
            "baseline": router_metrics(yt, base),
            "llm_on_same_items": router_metrics(yt, llm_held),
        }
    return out


# ------------------------------------------------------------------ gate sweep
def gate_sweep(scores: list[float], answerable: list[bool], thresholds: list[float] | None = None) -> list[dict]:
    """Abstain iff top score < threshold. Positive class = should abstain (unanswerable)."""
    s = np.asarray(scores, dtype=float)
    pos = ~np.asarray(answerable, dtype=bool)
    thrs = thresholds if thresholds is not None else [round(x, 3) for x in np.arange(0.0, 1.0001, 0.01)]
    out = []
    for t in thrs:
        pred = s < t
        tp, fp, fn = int((pred & pos).sum()), int((pred & ~pos).sum()), int((~pred & pos).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        n_ans = int((~pos).sum())
        out.append(
            {
                "threshold": float(t),
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "false_abstain_rate": fp / n_ans if n_ans else 0.0,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )
    return out


def best_threshold(sweep: list[dict]) -> dict:
    """Max abstain-F1; ties -> lowest threshold (fewest false abstains on answerable questions)."""
    return max(sweep, key=lambda r: (round(r["f1"], 9), -r["threshold"]))


def plot_sweep(sweep: list[dict], best: float, current: float | None, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    x = [r["threshold"] for r in sweep]
    fig, ax = plt.subplots(figsize=(6, 3.6), dpi=130)
    for key, label in (("precision", "abstain precision"), ("recall", "abstain recall"), ("f1", "abstain F1")):
        ax.plot(x, [r[key] for r in sweep], label=label, lw=2 if key == "f1" else 1.3)
    ax.axvline(best, color="k", ls="--", lw=1, label=f"best dev = {best:.2f}")
    if current is not None:
        ax.axvline(current, color="grey", ls=":", lw=1, label=f"config = {current:.2f}")
    ax.set_xlabel("rerank threshold (abstain if top score < t)")
    ax.set_ylim(0, 1.02)
    ax.legend(fontsize=7, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def score_gate(
    recs: list[dict], run_id: str = "run", gate_cfg: dict | None = None, fig_dir: Path | None = None
) -> dict:
    scores = [float(r["top_score"]) for r in recs]
    ans = [bool(r["answerable"]) for r in recs]
    sweep = gate_sweep(scores, ans)
    best = best_threshold(sweep)
    g = gate_cfg or {}
    cur_thr = g.get("rerank_threshold")
    out: dict = {
        "n": len(recs),
        "n_answerable": sum(ans),
        "n_unanswerable": len(ans) - sum(ans),
        "best": best,
        "sweep": sweep,
        "note": "tune gate.rerank_threshold on dev only; n_unanswerable is small, so the optimum is noisy",
    }
    if cur_thr is not None:
        out["at_config_threshold"] = min(sweep, key=lambda r: abs(r["threshold"] - cur_thr))
        out["config_threshold"] = cur_thr
    band = g.get("borderline")
    if band:
        lo, hi = band
        inb = [lo <= s <= hi for s in scores]
        out["borderline_band"] = list(band)
        out["frac_in_band"] = float(np.mean(inb)) if inb else None
        out["frac_in_band_answerable"] = (
            float(np.mean([b for b, a in zip(inb, ans, strict=True) if a])) if any(ans) else None
        )
        out["frac_in_band_unanswerable"] = (
            float(np.mean([b for b, a in zip(inb, ans, strict=True) if not a])) if not all(ans) else None
        )
    fd = fig_dir or FIG_DIR
    png = fd / f"{run_id}_gate_sweep.png"
    plot_sweep(sweep, best["threshold"], cur_thr, png)
    out["figure"] = str(png)
    return out


def plot_confusion(labels: list[str], matrix: list[list[int]], path: Path, title: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    m = np.asarray(matrix)
    fig, ax = plt.subplots(figsize=(5, 4.2), dpi=130)
    ax.imshow(m, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_xlabel("predicted")
    ax.set_ylabel("gold")
    ax.set_title(title, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(
                j,
                i,
                int(m[i, j]),
                ha="center",
                va="center",
                fontsize=8,
                color="white" if m[i, j] > m.max() / 2 else "black",
            )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ------------------------------------------------------------------ judgments
def load_tasks(store: RunStore, component: str) -> dict[str, dict]:
    return {t["task_id"]: t for t in read_jsonl(store.dir / f"judge_tasks_{component}.jsonl")}


def validate_judgment(j: dict, task: dict | None = None) -> list[str]:
    errs = []
    if not isinstance(j.get("task_id"), str):
        return ["missing task_id"]
    c = j.get("correctness")
    if not isinstance(c, int | float) or isinstance(c, bool) or not 1 <= c <= 5 or int(c) != c:
        errs.append("correctness must be an integer 1-5")
    kf = j.get("key_fact_supported")
    if not isinstance(kf, list) or not all(isinstance(x, bool) for x in kf):
        errs.append("key_fact_supported must be a list of booleans")
    elif task is not None and len(kf) != len(task.get("key_facts", [])):
        errs.append(f"key_fact_supported has {len(kf)} entries, task has {len(task.get('key_facts', []))} key_facts")
    cl = j.get("claims")
    if not isinstance(cl, list) or not all(isinstance(x, dict) and isinstance(x.get("supported"), bool) for x in cl):
        errs.append("claims must be a list of {text, supported: bool, citations_ok: bool|null}")
    elif any(x.get("citations_ok") not in (True, False, None) for x in cl):
        errs.append("claims[].citations_ok must be true/false/null")
    if not isinstance(j.get("language_ok"), bool):
        errs.append("language_ok must be boolean")
    if j.get("abstain_correct") not in (True, False, None):
        errs.append("abstain_correct must be true/false/null")
    return errs


def load_judgments(store: RunStore, component: str) -> tuple[dict[str, dict], list[str]]:
    """Merge reports/eval/runs/<run>/judgments_<component>_<k>.jsonl (later files win). Returns (by task_id, errors)."""
    tasks = load_tasks(store, component)
    merged: dict[str, dict] = {}
    errors: list[str] = []
    for p in sorted(store.dir.glob(f"judgments_{component}_*.jsonl")):
        for i, j in enumerate(read_jsonl(p), 1):
            errs = validate_judgment(j, tasks.get(j.get("task_id", "")))
            if j.get("task_id") and tasks and j["task_id"] not in tasks:
                errs.append("unknown task_id")
            if errs:
                errors.append(f"{p.name}:{i}: {'; '.join(errs)}")
                continue
            merged[j["task_id"]] = j
    return merged, errors


def task_id(component: str, item_id: str) -> str:
    return f"{component}:{item_id}"


def is_judgeable(rec: dict) -> bool:
    return rec.get("route") in JUDGED_ROUTES and not rec.get("abstained") and bool((rec.get("text") or "").strip())


def item_judgment(rec: dict, component: str, judgments: dict[str, dict]) -> dict | None:
    """Judged scores for one answerable item. Abstentions / wrong routes are scored automatically (correctness 1,
    recall 0). None = judgment still pending."""
    if not is_judgeable(rec):
        return {"correctness": 1, "recall": 0.0, "claims": [], "language_ok": True, "auto": True}
    j = judgments.get(task_id(component, rec["id"]))
    if j is None:
        return None
    kf = j["key_fact_supported"]
    return {
        "correctness": int(j["correctness"]),
        "recall": float(np.mean(kf)) if kf else None,
        "claims": j["claims"],
        "language_ok": j["language_ok"],
        "auto": False,
    }


def judged_metrics(recs: list[dict], component: str, judgments: dict[str, dict]) -> dict:
    scored = [(r, item_judgment(r, component, judgments)) for r in recs]
    done = [(r, s) for r, s in scored if s is not None]
    llm_judged = [s for _, s in done if not s["auto"]]
    claims = [c for s in llm_judged for c in s["claims"]]
    per_item_faith = [float(np.mean([c["supported"] for c in s["claims"]])) for s in llm_judged if s["claims"]]
    cit = [c["citations_ok"] for c in claims if c.get("citations_ok") is not None]
    return {
        "n_items": len(recs),
        "n_scored": len(done),
        "n_llm_judged": len(llm_judged),
        "n_pending": len(recs) - len(done),
        "mean_correctness": rate([float(s["correctness"]) for _, s in done]),
        "correct_ge4_rate": rate([float(s["correctness"] >= 4) for _, s in done]),
        "key_fact_recall": rate([s["recall"] for _, s in done if s["recall"] is not None]),
        "faithfulness_claim_level": rate([float(c["supported"]) for c in claims]),
        "faithfulness_item_mean": rate(per_item_faith),
        "fully_faithful_item_rate": rate([float(f == 1.0) for f in per_item_faith]),
        "citation_precision": rate([float(x) for x in cit]),
        "language_ok_rate": rate([float(s["language_ok"]) for s in llm_judged]),
        "correctness_hist": dict(sorted(Counter(int(s["correctness"]) for _, s in done).items())),
    }


# ------------------------------------------------------------------ answer / logistics / e2e
def _answered(r: dict) -> bool:
    return not r.get("abstained") and r.get("route") in JUDGED_ROUTES


def score_answer(
    recs: list[dict], judgments: dict[str, dict] | None = None, span=default_span, component: str = "answer"
) -> dict:
    qa = [r for r in recs if r.get("set") == "qa"]
    un = [r for r in recs if r.get("set") == "unanswerable"]
    judgments = judgments or {}
    out: dict = {"n": len(recs), "n_qa": len(qa), "n_unanswerable": len(un)}
    out.update(call_stats(recs))
    out["latency_s"] = latency_stats([r["latency_s"] for r in recs if "latency_s" in r])
    if qa:
        answered = [r for r in qa if _answered(r)]
        n_valid = sum(len(r.get("citations", [])) for r in answered)
        n_inv = sum(len(r.get("invalid_citations", [])) for r in answered)
        hit = [
            float(cites_gold([c["chunk_id"] for c in r.get("citations", [])], r["gold_chunk_ids"], span)) for r in qa
        ]
        out["qa"] = {
            "route_correct": rate([float(r["route"] == "content") for r in qa]),
            "abstain_rate_on_answerable": rate([float(bool(r.get("abstained"))) for r in qa]),
            "citation_validity_rate": (n_valid / (n_valid + n_inv)) if n_valid + n_inv else None,
            "n_citations": n_valid + n_inv,
            "answers_without_citation": rate([float(not r.get("citations")) for r in answered]),
            "gold_chunk_cited_rate": rate(hit),
            "gold_chunk_cited_rate_among_answered": rate(
                [
                    float(cites_gold([c["chunk_id"] for c in r.get("citations", [])], r["gold_chunk_ids"], span))
                    for r in answered
                ]
            ),
        }
        by_type: dict[str, list[float]] = {}
        for r, h in zip(qa, hit, strict=True):
            by_type.setdefault(r.get("type", "?"), []).append(h)
        out["qa"]["gold_chunk_cited_by_type"] = {
            k: {"n": len(v), "value": float(np.mean(v))} for k, v in sorted(by_type.items())
        }
        out["judged"] = judged_metrics(qa, component, judgments)
    if un:
        out["unanswerable"] = {
            "correct_abstain_rate": rate([float(bool(r.get("abstained")) or r.get("route") != "content") for r in un]),
            "answered_anyway_rate": rate([float(_answered(r) and r.get("route") == "content") for r in un]),
        }
    return out


def score_logistics(recs: list[dict], judgments: dict[str, dict] | None = None) -> dict:
    out: dict = {"n": len(recs)}
    out.update(call_stats(recs))
    out["latency_s"] = latency_stats([r["latency_s"] for r in recs if "latency_s" in r])
    out["route_correct"] = rate([float(r["route"] == "logistics") for r in recs])
    out["source_doc_cited"] = rate(
        [float(any(c["doc_id"] in set(r["gold_doc_ids"]) for c in r.get("citations", []))) for r in recs]
    )
    out["judged"] = judged_metrics(recs, "logistics", judgments or {})
    return out


def e2e_items(
    answer_recs: list[dict], logistics_recs: list[dict], ans_j: dict[str, dict], log_j: dict[str, dict]
) -> list[dict]:
    """Per-item e2e outcome: success True/False, or None when a judgment is still pending."""
    out = []
    for r in answer_recs:
        if r.get("set") == "unanswerable":
            ok: bool | None = bool(r.get("abstained")) or r.get("route") != "content"
            kind = "unanswerable"
        else:
            j = item_judgment(r, "answer", ans_j)
            ok = None if j is None else (r.get("route") == "content" and j["correctness"] >= 4)
            kind = "qa"
        out.append({"id": r["id"], "kind": kind, "success": ok, "rec": r})
    for r in logistics_recs:
        j = item_judgment(r, "logistics", log_j)
        ok = None if j is None else (r.get("route") == "logistics" and j["correctness"] >= 4)
        out.append({"id": r["id"], "kind": "logistics", "success": ok, "rec": r})
    return out


def score_e2e(answer_recs: list[dict], logistics_recs: list[dict], ans_j=None, log_j=None) -> dict:
    items = e2e_items(answer_recs, logistics_recs, ans_j or {}, log_j or {})
    recs = [i["rec"] for i in items]
    done = [i for i in items if i["success"] is not None]
    out: dict = {
        "n": len(items),
        "n_scored": len(done),
        "n_pending_judgment": len(items) - len(done),
        "success_rate": rate([float(i["success"]) for i in done]),
        "latency_s": latency_stats([r["latency_s"] for r in recs if "latency_s" in r]),
    }
    out.update(call_stats(recs))
    for kind in ("qa", "unanswerable", "logistics"):
        sub = [float(i["success"]) for i in done if i["kind"] == kind]
        out[f"success_{kind}"] = rate(sub)
    return out


# ------------------------------------------------------------------ verify (perturbation test)
def score_verify(recs: list[dict]) -> dict:
    out: dict = {"n": len(recs)}
    out.update(call_stats(recs))
    for kind in ("fabricated", "swapped"):
        rs = [r for r in recs if r.get(f"{kind}_detected") is not None]
        out[f"{kind}_detected"] = rate([float(r[f"{kind}_detected"]) for r in rs])
        out[f"{kind}_flagged_any"] = rate([float(r[f"{kind}_flagged_any"]) for r in rs])
    ctrl = [r for r in recs if r.get("control_flagged") is not None]
    if ctrl:
        out["control_false_alarm_rate"] = rate([float(r["control_flagged"]) for r in ctrl])
    return out


# ------------------------------------------------------------------ calibration
def _yn(v: str) -> bool | None:
    v = (v or "").strip().lower()
    return True if v in TRUE else False if v in FALSE else None


def judge_faithful(j: dict) -> bool:
    return all(c["supported"] for c in j["claims"])


def calibration_stats(csv_path: Path) -> dict | None:
    """Cohen's kappa (faithful y/n) and Spearman rho (correctness) between judge and human columns."""
    if not csv_path.exists():
        return None
    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fa, fb, ca, cb = [], [], [], []
    for r in rows:
        h, j = _yn(r.get("human_faithful", "")), _yn(r.get("judge_faithful", ""))
        if h is not None and j is not None:
            fa.append(j)
            fb.append(h)
        try:
            hc, jc = float(r.get("human_correctness", "")), float(r.get("judge_correctness", ""))
            ca.append(jc)
            cb.append(hc)
        except ValueError:
            pass
    out: dict = {"file": csv_path.name, "n_rows": len(rows), "n_faithful": len(fa), "n_correctness": len(ca)}
    out["kappa_faithful"] = M.cohen_kappa(fa, fb) if fa else None
    out["spearman_correctness"] = M.spearman(ca, cb) if len(ca) >= 3 else None
    return out


# ------------------------------------------------------------------ dispatcher
def _train_items_for_test(split: str) -> list[dict] | None:
    """Router baseline for test: train on the even half of the dev gold file."""
    if split == "dev":
        return None
    p = runs.ROOT / "eval" / "data" / "router_dev.jsonl"
    items = read_jsonl(p)
    return half_split([{"id": i["id"], "question": i["question"], "gold_route": i["route"]} for i in items])[0] or None


def score_component(
    run_id: str, component: str, split: str, root: Path | None = None, fig_dir: Path | None = None, gate_cfg=None
) -> dict:
    store = RunStore(run_id, root)
    load = lambda c: store.load(c, split)  # noqa: E731
    if component == "router":
        recs = load("router")
        rest = read_jsonl(store.dir / "router_rest.jsonl") or None
        out = score_router(recs, split, rest or _train_items_for_test(split))
        cm = out["confusion"]
        png = (fig_dir or FIG_DIR) / f"{run_id}_router_confusion_{split}.png"
        plot_confusion(cm["labels"], cm["matrix"], png, f"router {split} n={len(recs)}")
        out["figure"] = str(png)
    elif component == "gate":
        if gate_cfg is None:
            from app.config import cfg

            gate_cfg = cfg()["gate"]
        out = score_gate(load("gate"), f"{run_id}_{split}", gate_cfg, fig_dir)
    elif component == "answer":
        out = score_answer(load("answer"), load_judgments(store, "answer")[0])
    elif component == "logistics":
        out = score_logistics(load("logistics"), load_judgments(store, "logistics")[0])
    elif component == "verify":
        out = score_verify(load("verify"))
    elif component == "e2e":
        out = score_e2e(
            load("answer"), load("logistics"), load_judgments(store, "answer")[0], load_judgments(store, "logistics")[0]
        )
    else:
        raise ValueError(f"unknown component {component}")
    cal = sorted(runs.EVAL_DIR.glob(f"calibration_{run_id}*.csv")) if component == "answer" else []
    if cal:
        out["calibration"] = [calibration_stats(p) for p in cal]
    meta = store.meta()
    return clean(
        {
            "preset": meta.get("preset"),
            "gold_source": meta.get("gold_source", {}),
            "component": component,
            "split": split,
            "run_id": run_id,
            "prompts": (meta.get("config") or {}).get("prompts", {}),
            "models": (meta.get("config") or {}).get("models", {}),
            "metrics": out,
        }
    )


def write_result(res: dict) -> Path:
    runs.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    p = runs.EVAL_DIR / f"{date.today().isoformat()}_{res['component']}_{res['split']}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--component", required=True, choices=["router", "gate", "answer", "logistics", "verify", "e2e"])
    ap.add_argument("--run", default="latest")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--write", action="store_true", help="write reports/eval/<date>_<component>_<split>.json")
    ap.add_argument("--check-judgments", action="store_true")
    a = ap.parse_args()
    run_id = runs.resolve_run(a.run, a.component, a.split)
    store = RunStore(run_id)
    if a.check_judgments:
        comp = "logistics" if a.component == "logistics" else "answer"
        j, errs = load_judgments(store, comp)
        tasks = load_tasks(store, comp)
        missing = [t for t in tasks if t not in j]
        n_batch = 25
        order = list(tasks)
        bad_batches = sorted({order.index(t) // n_batch for t in missing})
        print(f"{run_id}: {len(j)}/{len(tasks)} tasks judged, {len(errs)} invalid lines")
        for e in errs[:30]:
            print("  invalid:", e)
        if missing:
            print(f"  missing {len(missing)} tasks; batches (25 tasks each, 0-based) to redo: {bad_batches}")
        raise SystemExit(1 if errs or missing else 0)
    res = score_component(run_id, a.component, a.split)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.write:
        print("wrote", write_result(res))


if __name__ == "__main__":
    main()
