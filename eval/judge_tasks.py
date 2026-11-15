"""[EVAL] Step 1 of offline judging: export judge tasks (no API calls), and calibration sheets for the human.

  uv run python -m eval.judge_tasks --run RUN_ID --component answer|logistics [--split dev]
      -> reports/eval/runs/<run_id>/judge_tasks_<component>.jsonl (sorted by item id; batch k = lines 25k..25k+24)
  uv run python -m eval.judge_tasks --run RUN_ID --component answer --calibration 20
      -> reports/eval/calibration_<run_id>.csv  (N random judged items, empty human columns)

Only real answers are exported (abstentions / wrong routes are scored automatically in eval.score).
Tasks never contain gold chunk/doc ids. Step 2: Haiku agents (skill judge-batch). Step 3: eval.score.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections.abc import Callable
from pathlib import Path

from eval import runs, score
from eval.runs import RunStore

PASSAGE_CHARS = 1500
BATCH = 25
CAL_COLUMNS = [
    "task_id", "question", "reference_answer", "system_answer", "passages",
    "human_correctness", "human_faithful", "human_notes", "judge_correctness", "judge_faithful",
]  # fmt: skip


def default_chunk_text(cid: str) -> tuple[str, str]:
    from app import store

    c = store.chunks().get(cid)
    return (c.breadcrumb, c.text) if c else ("", "")


def sentences_of(text: str) -> list[str]:
    try:
        from app.pipeline.verify import split_sentences

        return split_sentences(text)
    except Exception:  # noqa: BLE001
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]


def build_task(rec: dict, component: str, chunk_text: Callable[[str], tuple[str, str]] = default_chunk_text) -> dict:
    cited = {c["chunk_id"]: c for c in rec.get("citations", [])}
    in_prompt = (rec.get("debug") or {}).get("chunks_in_prompt") or []
    order = list(dict.fromkeys([*cited, *in_prompt]))
    passages = []
    for cid in order:
        crumb, text = chunk_text(cid)
        c = cited.get(cid, {})
        idx = in_prompt.index(cid) + 1 if cid in in_prompt else None
        passages.append(
            {
                "tag": c.get("tag") or (f"S{idx}" if idx else ""),
                "chunk_id": cid,
                "label": c.get("label") or crumb,
                "cited": cid in cited,
                "text": text[:PASSAGE_CHARS],
            }
        )
    passages.sort(key=lambda p: (not p["cited"], p["tag"]))
    return {
        "task_id": score.task_id(component, rec["id"]),
        "item_id": rec["id"],
        "component": component,
        "question": rec["question"],
        "reference_answer": rec.get("reference_answer"),
        "key_facts": rec.get("key_facts", []),
        "system_answer": rec["text"],
        "sentences": sentences_of(rec["text"]),
        "passages": passages,
    }


def build_tasks(recs: list[dict], component: str, chunk_text=default_chunk_text) -> list[dict]:
    recs = [r for r in recs if score.is_judgeable(r) and (component != "answer" or r.get("set") == "qa")]
    return [build_task(r, component, chunk_text) for r in sorted(recs, key=lambda r: r["id"])]


def write_tasks(store: RunStore, component: str, split: str, chunk_text=default_chunk_text) -> tuple[Path, int]:
    recs = store.load("logistics" if component == "logistics" else "answer", split)
    tasks = build_tasks(recs, component, chunk_text)
    p = store.dir / f"judge_tasks_{component}.jsonl"
    p.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks), encoding="utf-8")
    return p, len(tasks)


def write_calibration(store: RunStore, component: str, n: int, seed: int = 0, out_dir: Path | None = None) -> Path:
    tasks = score.load_tasks(store, component)
    judg, _ = score.load_judgments(store, component)
    ids = sorted(t for t in judg if t in tasks)
    if not ids:
        raise SystemExit("no judged items yet: run the judge-batch step first")
    picked = random.Random(seed).sample(ids, min(n, len(ids)))
    d = out_dir or runs.EVAL_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"calibration_{store.run_id}.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, CAL_COLUMNS)
        w.writeheader()
        for tid in picked:
            t, j = tasks[tid], judg[tid]
            w.writerow(
                {
                    "task_id": tid,
                    "question": t["question"],
                    "reference_answer": t["reference_answer"],
                    "system_answer": t["system_answer"],
                    "passages": "\n---\n".join(f"[{q['tag']}] {q['text'][:400]}" for q in t["passages"] if q["cited"]),
                    "human_correctness": "",
                    "human_faithful": "",
                    "human_notes": "",
                    "judge_correctness": j["correctness"],
                    "judge_faithful": "yes" if score.judge_faithful(j) else "no",
                }
            )
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="latest")
    ap.add_argument("--component", default="answer", choices=["answer", "logistics"])
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--calibration", type=int, metavar="N")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    src = "logistics" if a.component == "logistics" else "answer"
    store = RunStore(runs.resolve_run(a.run, src, a.split))
    if a.calibration:
        print("wrote", write_calibration(store, a.component, a.calibration, a.seed))
        print("Fill human_correctness (1-5) and human_faithful (yes/no); eval.score then reports kappa and Spearman.")
        return
    p, n = write_tasks(store, a.component, a.split)
    print(f"wrote {p}: {n} tasks -> {-(-n // BATCH)} batches of {BATCH} (judgments_{a.component}_<k>.jsonl, k = 0..)")


if __name__ == "__main__":
    main()
