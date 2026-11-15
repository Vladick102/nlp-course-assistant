---
name: add-gold-items
description: Generate candidate eval items (QA / router / unanswerable / logistics) from given slides into a review file for human approval.
---
# add-gold-items
Args: `<set> <n> [doc_ids...]` — set ∈ qa, router, unanswerable, logistics.

Rules (PLAN.md §6.1):
- Write ONLY to `eval/data/review/<set>_candidates.jsonl`. Never write to `eval/data/*test*` or `*dev*` — a human promotes items.
- qa: sample slides (stratify by course and doc_type; include figure slides). Question must be **paraphrased** — no 4+-word
  span copied from the slide (check automatically and reject). Fields: `id, question, gold_chunk_ids, reference_answer,
  key_facts[], type (single|figure|multi|real), lang`. ~15% English/mixed.
- unanswerable: on-topic OS/architecture questions; verify with `retrieve.run(mode="bm25")` + reading top-5 that the slides
  don't answer them; record the evidence check in `notes`.
- router: label ∈ content/logistics/navigation/clarify/off_topic; include hard negatives and injections.
- Use `app/llm.py` with role "judge" (a model different from the generator) via `prompts/gold_*.md`.
- Finish with counts per type and a reminder that items need human review.
