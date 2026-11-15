---
name: run-eval
description: Run the evaluation for one component (or all) on dev or test, compare with the previous run and log the delta in reports/eval/history.md.
---
# run-eval
Args: `<component> [dev|test] "<what changed>"` — component ∈ parser, figures, router, retrieval, gate, answer, verify, logistics, e2e, all.

1. Check `git status` / note uncommitted changes and current prompt versions (`grep -h '^version' prompts/*.md`).
2. Run `uv run python -m eval.run --component <component> --split <split>` (default split: dev).
   Results land in `reports/eval/<date>_<component>_<split>.json` and `reports/eval/summary.md` is regenerated.
3. Find the previous result for the same component+split; compute deltas for the headline metrics (PLAN.md §1.4 table).
4. Append one row to `reports/eval/history.md`:
   `| date | component | split | change | metric: before → after | kept? |`. "kept?" = yes only if the headline metric
   did not drop beyond its bootstrap CI and no guard metric (false-reject rate, faithfulness) regressed.
5. Never run `--split test` while tuning; test is reported once per iteration (AGENTS.md §3).
