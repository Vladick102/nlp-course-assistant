"""[EVAL] Regenerate reports/eval/summary.md from the latest run dirs; optionally append to reports/eval/history.md.

uv run python -m eval.report                       # rewrite summary.md
uv run python -m eval.report --log "what changed" [--kept yes|no|tbd] [--component C] [--split dev]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from eval import runs, score

COMPONENTS = ["router", "gate", "answer", "logistics", "verify", "e2e"]
# headline metric per component: (label, path into result["metrics"])
HEADLINE = {
    "router": ("accuracy", ("accuracy", "value")),
    "gate": ("abstain F1 @best thr", ("best", "f1")),
    "answer": ("correct>=4 rate", ("judged", "correct_ge4_rate", "value")),
    "logistics": ("source doc cited", ("source_doc_cited", "value")),
    "verify": ("fabricated detected", ("fabricated_detected", "value")),
    "e2e": ("success rate", ("success_rate", "value")),
}
SMALL_NOTE = "small-sample run: differences within CI are not significant"
SKIP_KEYS = {
    "sweep",
    "confusion",
    "per_class",
    "figure",
    "baseline",
    "calibration",
    "models_served",
    "correctness_hist",
}


def fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, dict) and "value" in v:
        if v["value"] is None:
            return f"- (n={v.get('n', 0)})"
        n = v.get("n", "?")
        if v.get("lo") is None or v.get("hi") is None:
            return f"{v['value']:.3f} (n={n})"
        return f"{v['value']:.3f} [{v['lo']:.3f}, {v['hi']:.3f}] (n={n})"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def flat_rows(m: dict, prefix: str = "") -> list[tuple[str, str]]:
    rows = []
    for k, v in m.items():
        if k in SKIP_KEYS:
            continue
        key = f"{prefix}{k}"
        if isinstance(v, dict) and "value" not in v:
            rows += flat_rows(v, key + ".")
        elif isinstance(v, list):
            continue
        else:
            rows.append((key, fmt(v)))
    return rows


def table(rows: list[tuple[str, str]]) -> list[str]:
    return ["| metric | value |", "|---|---|", *[f"| {k} | {v} |" for k, v in rows], ""]


def headline(res: dict) -> tuple[str, float | None]:
    label, path = HEADLINE[res["component"]]
    v = res["metrics"]
    for p in path:
        v = v.get(p) if isinstance(v, dict) else None
    return label, v


def section(res: dict) -> list[str]:
    m = res["metrics"]
    prompts = ", ".join(f"{k} v{v}" for k, v in sorted((res.get("prompts") or {}).items())) or "-"
    gold = ", ".join(f"{k}: {v}" for k, v in (res.get("gold_source") or {}).items()) or "-"
    n = m.get("n", "?")
    out = [
        f"### {res['component']} - split `{res['split']}`, n={n}",
        f"run_id `{res['run_id']}`{' (preset ' + res['preset'] + ')' if res.get('preset') else ''}; gold: {gold}; "
        f"models: {', '.join(f'{k}={v}' for k, v in (res.get('models') or {}).items() if k in ('fast', 'generator'))}",
        f"prompts: {prompts}",
        "",
    ]
    out += table(flat_rows(m))
    if res["component"] == "router":
        out += ["| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
        out += [
            f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |"
            for k, v in m.get("per_class", {}).items()
        ]
        out.append("")
        cm = m.get("confusion")
        if cm:
            out += ["Confusion (rows gold, cols predicted): " + ", ".join(cm["labels"])]
            out += ["", *[f"    {r}" for r in cm["matrix"]], ""]
        b = m.get("baseline")
        if b:
            out += [
                f"Baseline {b['kind']} (train n={b['train_n']}, eval n={b['eval_n']}): accuracy "
                f"{fmt(b['baseline']['accuracy'])}, macro-F1 {b['baseline']['macro_f1']:.3f}; "
                f"LLM on the same items: accuracy {fmt(b['llm_on_same_items']['accuracy'])}, "
                f"macro-F1 {b['llm_on_same_items']['macro_f1']:.3f}",
                "",
            ]
        if m.get("models_served"):
            out += [f"Models that served the calls: {m['models_served']}", ""]
    if res["component"] == "gate":
        b = m["best"]
        out += [
            f"Best dev threshold {b['threshold']:.2f}: abstain precision {b['precision']:.2f}, "
            f"recall {b['recall']:.2f}, "
            f"F1 {b['f1']:.2f}, false-abstain rate {b['false_abstain_rate']:.2f}. {m.get('note', '')}",
            "",
        ]
    if m.get("figure"):
        out += [f"Figure: `{m['figure']}`", ""]
    for cal in m.get("calibration") or []:
        out += [
            f"Human calibration `{cal['file']}`: kappa(faithful)={fmt(cal['kappa_faithful'])} "
            f"(n={cal['n_faithful']}), Spearman(correctness)={fmt(cal['spearman_correctness'])} "
            f"(n={cal['n_correctness']})",
            "",
        ]
    return out


def collect(root: Path | None = None) -> list[dict]:
    results = []
    for comp in COMPONENTS:
        for split in ("dev", "test"):
            src = {"e2e": "answer"}.get(comp, comp)
            rid = runs.latest_run(src, split, root)
            if rid:
                results.append(score.score_component(rid, comp, split, root))
    return results


def render(results: list[dict]) -> str:
    out = [f"# Evaluation summary (generated {date.today()} by `python -m eval.report`)", ""]
    small = any(r.get("preset") for r in results) or any((r["metrics"].get("n") or 0) < 50 for r in results)
    drafts = {s for r in results for s, v in (r.get("gold_source") or {}).items() if "draft" in v}
    if drafts:
        out += [f"> **gold = unreviewed draft** ({', '.join(sorted(drafts))}); numbers are provisional.", ""]
    if small:
        out += [f"> {SMALL_NOTE}. All intervals are 95% bootstrap CIs over items.", ""]
    if not results:
        out += ["_No runs yet. Start with `uv run python -m eval.run --component all --split dev --preset small`._", ""]
    out += ["| component | split | n | run_id | headline |", "|---|---|---|---|---|"]
    for r in results:
        label, v = headline(r)
        out.append(
            f"| {r['component']} | {r['split']} | {r['metrics'].get('n', '?')} | `{r['run_id']}` | {label}: {fmt(v)} |"
        )
    out.append("")
    for r in results:
        out += section(r)
    others = []
    for pat in ("parser_*.json", "retrieval*.json", "figure*.json"):
        files = sorted(runs.EVAL_DIR.glob(pat))
        if files:
            others.append(f"- latest `{files[-1].name}` ({pat})")
    if others:
        out += ["## Other component reports (own scripts)", *others, ""]
    return "\n".join(out)


def write_summary(root: Path | None = None, out: Path | None = None) -> Path:
    p = out or runs.EVAL_DIR / "summary.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(collect(root)), encoding="utf-8")
    return p


HISTORY_HEADER = "| date | component | split | change | metric: before → after | kept? |\n|---|---|---|---|---|---|\n"


def append_history(results: list[dict], change: str, kept: str = "tbd", path: Path | None = None) -> list[str]:
    p = path or runs.EVAL_DIR / "history.md"
    old = p.read_text(encoding="utf-8") if p.exists() else HISTORY_HEADER
    rows = []
    for r in results:
        label, v = headline(r)
        before = "n/a"
        for ln in reversed(old.splitlines()):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) >= 6 and cells[1] == r["component"] and cells[2] == r["split"] and "→" in cells[4]:
                before = cells[4].split("→")[-1].strip()
                break
        after = "n/a" if v is None else f"{v:.3f}"
        rows.append(
            f"| {date.today()} | {r['component']} | {r['split']} | {change} | {label}: {before} → {after} | {kept} |"
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(old.rstrip("\n") + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", metavar="CHANGE", help="append a row per component to reports/eval/history.md")
    ap.add_argument("--kept", default="tbd", choices=["yes", "no", "tbd"])
    ap.add_argument("--component", choices=COMPONENTS)
    ap.add_argument("--split", choices=["dev", "test"])
    a = ap.parse_args()
    results = collect()
    p = runs.EVAL_DIR / "summary.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(results), encoding="utf-8")
    print("wrote", p)
    if a.log:
        sel = [
            r
            for r in results
            if (not a.component or r["component"] == a.component) and (not a.split or r["split"] == a.split)
        ]
        for row in append_history(sel, a.log, a.kept):
            print(row)


if __name__ == "__main__":
    main()
