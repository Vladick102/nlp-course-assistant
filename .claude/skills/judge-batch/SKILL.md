---
name: judge-batch
description: Judge one batch (about 25) of eval answer tasks offline with the strict rubric in prompts/judge_answer.md and write judgments JSONL. For Haiku judge agents; no API calls.
---
# judge-batch
Args: `<run_id> <component: answer|logistics> <k>` - judge batch `k` (0-based) of `reports/eval/runs/<run_id>/judge_tasks_<component>.jsonl`.

You are a Haiku judge agent. Offline work only: do NOT call any LLM API, do NOT run the pipeline, do NOT open gold files
(`eval/data/**`), other runs, or `judgments_*` files of other batches. Use only the task lines.

Steps
1. Read `prompts/judge_answer.md` completely (the rubric; version in its front matter). It is binding. Never use outside
   knowledge; never "fix" the reference.
2. Read lines `25k+1 .. 25k+25` of the tasks file (`sed -n '<a>,<b>p'`); each line is one task. Fewer lines in the last batch.
3. For every task, in order, produce ONE judgment object exactly as specified in the rubric's OUTPUT section:
   `task_id`, `correctness` (int 1-5), `key_fact_supported` (booleans, same length and order as the task's `key_facts`),
   `claims` (per factual sentence: `text`, `supported`, `citations_ok`), `language_ok`, `abstain_correct`, `notes`.
   Judge each task on its own; do not let earlier tasks calibrate later ones.
4. Write all judgments, one JSON per line (UTF-8, no code fences), to
   `reports/eval/runs/<run_id>/judgments_<component>_<k>.jsonl`. Exactly one line per task, none skipped.
5. Validate: `uv run python -m eval.score --component <component> --run <run_id> --check-judgments`. Fix every invalid line of YOUR
   batch (shape errors, wrong key_fact_supported length) and re-run. Lines of other batches are not your concern.
6. Reply with at most 3 lines: batch k, number of tasks judged, number of validation errors left.

Coordinator (Haiku, <=6 concurrent workers): run `uv run python -m eval.judge_tasks --run <run_id> --component <c>` first (it prints
the batch count), launch one worker per batch with this skill, then `--check-judgments`; it lists the batches still missing
or invalid - re-launch each such batch once. Then `uv run python -m eval.score --component <c> --run <run_id> --write`
and `uv run python -m eval.report`. For human calibration: `eval.judge_tasks --calibration 20`.
