# Evaluation summary (generated 2026-11-15 by `python -m eval.report`)

> **gold = unreviewed draft** (logistics, qa, router, unanswerable); numbers are provisional.

> small-sample run: differences within CI are not significant. All intervals are 95% bootstrap CIs over items.

| component | split | n | run_id | headline |
|---|---|---|---|---|
| router | dev | 20 | `2026-11-15_nogit_dead0146_small` | accuracy: 0.950 |
| gate | dev | 145 | `2026-11-15_nogit_6418daca` | abstain F1 @best thr: 0.868 |
| answer | dev | 17 | `2026-11-15_nogit_1887d8e5_small` | correct>=4 rate: 0.750 |
| logistics | dev | 5 | `2026-11-15_nogit_1887d8e5_small` | source doc cited: 0.800 |
| verify | dev | 1 | `2026-11-15_nogit_1887d8e5_small` | fabricated detected: 1.000 |
| e2e | dev | 22 | `2026-11-15_nogit_1887d8e5_small` | success rate: 0.773 |

### router - split `dev`, n=20
run_id `2026-11-15_nogit_dead0146_small` (preset small); gold: router: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 20 |
| accuracy | 0.950 [0.850, 1.000] (n=20) |
| macro_f1 | 0.949 |
| false_reject_rate | 0.000 [0.000, 0.000] (n=12) |
| latency_s.p50 | 10.035 |
| latency_s.p95 | 128.710 |
| latency_s.mean | 27.557 |
| calls_per_item | 1.000 |
| live_calls_per_item | 1.000 |
| total_calls | 20 |
| total_live_calls | 20 |
| hard_accuracy | 1.000 [1.000, 1.000] (n=5) |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| content | 1.00 | 1.00 | 1.00 | 4 |
| logistics | 0.80 | 1.00 | 0.89 | 4 |
| navigation | 1.00 | 0.75 | 0.86 | 4 |
| clarify | 1.00 | 1.00 | 1.00 | 4 |
| off_topic | 1.00 | 1.00 | 1.00 | 4 |

Confusion (rows gold, cols predicted): content, logistics, navigation, clarify, off_topic

    [4, 0, 0, 0, 0]
    [0, 4, 0, 0, 0]
    [0, 1, 3, 0, 0]
    [0, 0, 0, 4, 0]
    [0, 0, 0, 0, 4]

Baseline tfidf+logreg (train n=130, eval n=20): accuracy 0.650 [0.450, 0.850] (n=20), macro-F1 0.625; LLM on the same items: accuracy 0.950 [0.850, 1.000] (n=20), macro-F1 0.949

Models that served the calls: {'inclusionai/ling-3.2-flash:free': 17, 'nvidia/nemotron-3-ultra-550b-a55b:free': 3}

Figure: `/home/vsydora/projects/nlp/HW1/reports/eval/figures/2026-11-15_nogit_dead0146_small_router_confusion_dev.png`

### gate - split `dev`, n=145
run_id `2026-11-15_nogit_6418daca`; gold: qa: unreviewed draft, unanswerable: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 145 |
| n_answerable | 120 |
| n_unanswerable | 25 |
| best.threshold | 0.170 |
| best.precision | 0.821 |
| best.recall | 0.920 |
| best.f1 | 0.868 |
| best.false_abstain_rate | 0.042 |
| best.tp | 23 |
| best.fp | 5 |
| best.fn | 2 |
| note | tune gate.rerank_threshold on dev only; n_unanswerable is small, so the optimum is noisy |
| at_config_threshold.threshold | 0.170 |
| at_config_threshold.precision | 0.821 |
| at_config_threshold.recall | 0.920 |
| at_config_threshold.f1 | 0.868 |
| at_config_threshold.false_abstain_rate | 0.042 |
| at_config_threshold.tp | 23 |
| at_config_threshold.fp | 5 |
| at_config_threshold.fn | 2 |
| config_threshold | 0.170 |
| frac_in_band | 0.048 |
| frac_in_band_answerable | 0.042 |
| frac_in_band_unanswerable | 0.080 |

Best dev threshold 0.17: abstain precision 0.82, recall 0.92, F1 0.87, false-abstain rate 0.04. tune gate.rerank_threshold on dev only; n_unanswerable is small, so the optimum is noisy

Figure: `/home/vsydora/projects/nlp/HW1/reports/eval/figures/2026-11-15_nogit_6418daca_dev_gate_sweep.png`

### answer - split `dev`, n=17
run_id `2026-11-15_nogit_1887d8e5_small` (preset small); gold: logistics: unreviewed draft, qa: unreviewed draft, unanswerable: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 17 |
| n_qa | 12 |
| n_unanswerable | 5 |
| calls_per_item | 1.824 |
| live_calls_per_item | 1.824 |
| total_calls | 31 |
| total_live_calls | 31 |
| latency_s.p50 | 63.364 |
| latency_s.p95 | 152.176 |
| latency_s.mean | 67.177 |
| qa.route_correct | 0.833 [0.583, 1.000] (n=12) |
| qa.abstain_rate_on_answerable | 0.000 [0.000, 0.000] (n=12) |
| qa.citation_validity_rate | 1.000 |
| qa.n_citations | 25 |
| qa.answers_without_citation | 0.000 [0.000, 0.000] (n=10) |
| qa.gold_chunk_cited_rate | 0.750 [0.500, 1.000] (n=12) |
| qa.gold_chunk_cited_rate_among_answered | 0.900 [0.700, 1.000] (n=10) |
| qa.gold_chunk_cited_by_type.multi | 0.667 (n=3) |
| qa.gold_chunk_cited_by_type.real | 0.667 (n=3) |
| qa.gold_chunk_cited_by_type.single | 0.667 (n=3) |
| judged.n_items | 12 |
| judged.n_scored | 12 |
| judged.n_llm_judged | 10 |
| judged.n_pending | 0 |
| judged.mean_correctness | 3.667 [2.917, 4.333] (n=12) |
| judged.correct_ge4_rate | 0.750 [0.500, 1.000] (n=12) |
| judged.key_fact_recall | 0.667 [0.472, 0.861] (n=12) |
| judged.faithfulness_claim_level | 0.915 [0.809, 0.979] (n=47) |
| judged.faithfulness_item_mean | 0.905 [0.788, 1.000] (n=10) |
| judged.fully_faithful_item_rate | 0.700 [0.400, 1.000] (n=10) |
| judged.citation_precision | 0.833 [0.714, 0.929] (n=42) |
| judged.language_ok_rate | 1.000 [1.000, 1.000] (n=10) |
| unanswerable.correct_abstain_rate | 1.000 [1.000, 1.000] (n=5) |
| unanswerable.answered_anyway_rate | 0.000 [0.000, 0.000] (n=5) |

### logistics - split `dev`, n=5
run_id `2026-11-15_nogit_1887d8e5_small` (preset small); gold: logistics: unreviewed draft, qa: unreviewed draft, unanswerable: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 5 |
| calls_per_item | 2.000 |
| live_calls_per_item | 1.800 |
| total_calls | 10 |
| total_live_calls | 9 |
| latency_s.p50 | 44.272 |
| latency_s.p95 | 124.051 |
| latency_s.mean | 68.723 |
| route_correct | 1.000 [1.000, 1.000] (n=5) |
| source_doc_cited | 0.800 [0.400, 1.000] (n=5) |
| judged.n_items | 5 |
| judged.n_scored | 5 |
| judged.n_llm_judged | 4 |
| judged.n_pending | 0 |
| judged.mean_correctness | 3.200 [2.000, 4.400] (n=5) |
| judged.correct_ge4_rate | 0.600 [0.200, 1.000] (n=5) |
| judged.key_fact_recall | 0.533 [0.267, 0.800] (n=5) |
| judged.faithfulness_claim_level | 0.727 [0.455, 1.000] (n=11) |
| judged.faithfulness_item_mean | 0.708 [0.250, 1.000] (n=4) |
| judged.fully_faithful_item_rate | 0.500 [0.000, 1.000] (n=4) |
| judged.citation_precision | 0.727 [0.455, 1.000] (n=11) |
| judged.language_ok_rate | 1.000 [1.000, 1.000] (n=4) |

### verify - split `dev`, n=1
run_id `2026-11-15_nogit_1887d8e5_small` (preset small); gold: logistics: unreviewed draft, qa: unreviewed draft, unanswerable: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 1 |
| calls_per_item | 1.000 |
| live_calls_per_item | 1.000 |
| total_calls | 1 |
| total_live_calls | 1 |
| fabricated_detected | 1.000 [1.000, 1.000] (n=1) |
| fabricated_flagged_any | 1.000 [1.000, 1.000] (n=1) |
| swapped_detected | - (n=0) |
| swapped_flagged_any | - (n=0) |

### e2e - split `dev`, n=22
run_id `2026-11-15_nogit_1887d8e5_small` (preset small); gold: logistics: unreviewed draft, qa: unreviewed draft, unanswerable: unreviewed draft; models: fast=inclusionai/ling-3.2-flash:free, generator=inclusionai/ling-3.2-flash:free
prompts: answer v2, gate v1, judge_answer v1, judge_figure v1, logistics v2, navigate v1, rewrite v1, route_rewrite v1, router v1, verify v1, vlm_figure v1

| metric | value |
|---|---|
| n | 22 |
| n_scored | 22 |
| n_pending_judgment | 0 |
| success_rate | 0.773 [0.591, 0.909] (n=22) |
| latency_s.p50 | 56.856 |
| latency_s.p95 | 145.873 |
| latency_s.mean | 67.529 |
| calls_per_item | 1.864 |
| live_calls_per_item | 1.818 |
| total_calls | 41 |
| total_live_calls | 40 |
| success_qa | 0.750 [0.500, 1.000] (n=12) |
| success_unanswerable | 1.000 [1.000, 1.000] (n=5) |
| success_logistics | 0.600 [0.200, 1.000] (n=5) |

## Other component reports (own scripts)
- latest `parser_2026-11-15.json` (parser_*.json)
- latest `retrieval_2026-11-15_dev_fast.json` (retrieval*.json)
- latest `figure_2026-11-15.json` (figure*.json)
