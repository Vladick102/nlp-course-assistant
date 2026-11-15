# Gold evaluation sets — schema (contract between gold builders and eval code)

Drafts land in `eval/data/review/<set>.jsonl`; after human review they are split and promoted to
`eval/data/<set>_dev.jsonl` / `eval/data/<set>_test.jsonl` (test files are frozen — AGENTS.md §7).
Chunk ids follow `data/index/chunks.jsonl`: `<doc_id>#<page_start>` (slide) or `<doc_id>#w<page>` (window).

| Set | Fields |
|---|---|
| `qa` | `id` (qa-NNN), `question`, `gold_chunk_ids` [≥1, any of them counts as a hit], `reference_answer` (UA, 1–3 sentences), `key_facts` [2–4 short atomic facts], `type` ∈ single/figure/multi/real, `course` ∈ pok/aks/os, `lang` ∈ uk/en/mixed, `notes` |
| `unanswerable` | `id` (un-NNN), `question`, `course`, `evidence` (what was searched and why the slides don't answer it), `nearest_chunk_ids` [top hits that look related but don't answer] |
| `logistics` | `id` (lo-NNN), `question`, `course`, `gold_doc_ids` [syllabus_* / requirements_2024_2025], `gold_chunk_ids`, `key_facts`, `reference_answer` |
| `router` | `id` (ro-NNN), `question`, `history` [list of {role, content}] (may be empty), `route` ∈ content/logistics/navigation/clarify/off_topic, `course` ∈ pok/aks/os/null, `hard` (bool: deliberately tricky), `notes` |
| `parse_gold` | see eval/parse_eval.py |
| `figure_gold` | see eval/figure_eval.py |

Rules: questions are **paraphrased** (no 4+ consecutive words copied from the slide); ~15% English or mixed;
the builder never looks at system outputs (answers/retrieval rankings) when writing gold labels — except the
unanswerable set, where a BM25 search is used *only* to verify the answer is absent.
