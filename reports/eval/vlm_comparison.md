# VLM comparison for figure-slide descriptions: INCOMPLETE (2026-11-15)

**Phase:** [EVAL] (model comparison before the full ~1,073-slide VLM pass).
**Status:** the comparison did not finish. No model recommendation is made in this report.

## What happened

- Candidates: `google/gemini-3.6-flash`, `anthropic/claude-sonnet-5.5`, `openai/gpt-5.4-mini`.
- Gold: `eval/data/review/figure_gold.jsonl`, 30 items (3 decorative, 27 figure slides). This is a **DRAFT gold set not yet reviewed by a human**.
- Judges (planned, to control self-preference): `anthropic/claude-sonnet-5.5` and `openai/gpt-5.4`.
- Script: `scripts/compare_vlm.py`. Raw output: `reports/eval/vlm_comparison_2026-11-15.json`.
- The full run hit OpenRouter HTTP 402 ("would exceed your available credits") after the first few dozen calls. The OpenRouter credits endpoint reports `total_credits: 0` for the account. Calls that succeeded before that point are cached. The run was stopped there and not retried, so no further spend happens without a decision from the user.

## Completed before the stop

| candidate | descriptions ok / 30 | judged (Sonnet / GPT-5.4) | mean latency (s, uncached) | cost per description (USD) |
|---|---|---|---|---|
| google/gemini-3.6-flash | 15 | 14 / 14 | 5.9 | 0.0023 |
| anthropic/claude-sonnet-5.5 | 7 | 4 / 4 | 3.2 | 0.0052 |
| openai/gpt-5.4-mini | 7 | 4 / 4 | 4.3 | 0.0015 |

These counts are not comparable across candidates: each candidate got a different subset of items because the credit failure hit them at different points. The JSON summary counts the 402 errors as entity-recall 0, so its recall and faithfulness numbers reflect the outage and must not be read as model quality.

Spend for all vlmcmp runs (two smoke runs and the partial full run): about $0.11 (descriptions $0.081, judges $0.028).

## Smoke run (3 items, evenly spaced, all candidates and both judges)

Projected cost for the full 30-item run was $0.29 against the $5 budget. Projected description cost for 1,073 slides, from the second smoke run: Gemini about $2.3, Sonnet about $7.5, GPT-5.4-mini about $1.9. These are per-description estimates from few calls, so treat them as rough.

## To finish

1. Restore OpenRouter credits for the key in `.env`.
2. Rerun `uv run python scripts/compare_vlm.py`. Successful calls are cached, so only the missing descriptions and judgments are paid for (roughly $0.2 to $0.3 for the remaining descriptions and judgments).
3. Caveat for that rerun: cached calls log `latency_s` as 0 and are excluded from the latency stats, so latency would be computed only on the newly generated calls. For clean latency, clear the cache entries for the 30 items first, or accept a smaller n for latency.

## Implementation notes (for the full comparison)

- `override_models` disables the `reasoning` setting for non-Google candidates and for both judges, so Gemini runs with `effort: minimal` (per config) and the others with provider defaults. Judges also run without the configured `effort: low`. This is a confound to keep in mind when reading the results.
- Entity recall: over the 27 non-decorative gold items. Decorative or errored outputs score 0.
- Decorative accuracy: over all 30 items. Errors count as incorrect.
- Faithfulness and critical hallucination: only on non-decorative, non-error outputs.

## Problems found (not fixed, outside my ownership)

- `eval/figure_eval.py`: `main()` calls `argparse` but the module never imports it, so the CLI raises `NameError`. Its `DEFAULT_GOLD` (`eval/data/figure_gold.jsonl`) does not exist; the gold file is in `eval/data/review/`.
- The same OpenRouter key was also used by an unrelated `answer` call (`anthropic/claude-haiku-5.5`) in the same window, so the app or another process was spending credits at the same time.
