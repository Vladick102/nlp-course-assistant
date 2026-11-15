---
name: error-analysis
description: Classify the lowest-scoring items of the latest eval run by error taxonomy and propose the single most impactful fix.
---
# error-analysis
Args: `<component> [n=20]`.

1. Load the latest `reports/eval/*_<component>_dev.json`; take the n worst items (lowest score / failed).
2. For each, open its trace (`trace_id` field) with the `trace-debug` procedure, and label ONE root cause:
   `retrieval_miss` (gold slide not in top-30) · `ranking` (in top-30, not in top-k) · `parsing_loss` (text missing in chunk) ·
   `figure_desc` (needed info only in an image; description wrong/missing) · `router` · `gate_false_abstain` ·
   `gate_false_answer` · `generator_ignored_context` · `citation_error` · `gold_error` · `judge_error`.
3. Write `reports/eval/error_analysis_<component>_<date>.md`: counts per cause, 2–3 representative examples each, and
   ONE proposed fix targeting the largest bucket, with the metric expected to move. `gold_error` items go to
   `eval/data/review/gold_issues.jsonl` for a human — do not edit gold files.
