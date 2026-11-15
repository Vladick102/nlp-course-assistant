# Figure descriptions (tracked in git — not cheaply reproducible)

Produced by Claude Code **Haiku sub-agents** looking at rendered slide images (the user chose this over a paid
OpenRouter VLM). Rules for the describer = `prompts/vlm_figure.md` (same rubric the API path would use).

- `batches/batch_NN.jsonl` — input manifest: `{doc_id, page, pdf_path, title, slide_text}` (slides with `needs_vision`).
- `out/batch_NN.jsonl` — agent output: `{doc_id, page, description}`; `description == "ДЕКОРАТИВНЕ"` for decorative visuals.
- Imported into `data/parsed/<doc_id>/slides.jsonl` (`figure_description`) by the importer, then `make index`.
- `batches/pilot.jsonl` = the 30 slides of `eval/data/review/figure_gold.jsonl` (quality + token-cost pilot).
