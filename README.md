# Course Assistant

Streamlit chat app that answers Ukrainian students' questions about three courses (ПОК, АКС, ОС) strictly from the lecture/lab/syllabus materials, with slide citations and abstention. Design: `PLAN.md`; results: `reports/report.md`; agent rules: `AGENTS.md`.

## Prerequisites
- Linux, Python 3.12 (managed by `uv`), [`uv`](https://docs.astral.sh/uv/)
- LibreOffice (`soffice` on PATH) to convert `.pptx`/`.docx` to PDF
- About 6 GB free disk for the local models (`BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3`, downloaded from Hugging Face on first use) plus the generated data
- CPU is enough (torch CPU build); dense encoding of the chunks took about 35 minutes on CPU, and reranking takes 20-35 s per query
- An OpenRouter API key (free models only)

## Setup
```bash
uv sync
cp .env.example .env        # then put your key in .env: OPENROUTER_API_KEY=sk-or-...
```
Raw course files are in `pok/`, `aks/`, `os/` (read-only; never modify them). Model ids, thresholds and paths are in `config.yaml`.

## Build the data (offline)
```bash
make convert ingest index
```
- `convert`: pptx/docx to PDF in `data/converted/`
- `ingest`: registry, parser, figure flags; re-applies the tracked figure descriptions from `data/figure_descriptions/out/` (made by Claude Code Haiku agents; no API call needed)
- `index`: chunks, catalog, BM25 and bge-m3 vectors in `data/index/`

`make vlm` is the optional API path for figure descriptions; it is not needed.
Generated folders (`data/converted`, `data/parsed`, `data/index`, `data/cache`, `logs`) are git-ignored.

## Run the app
```bash
make ui                     # streamlit run app/ui.py
```
Sidebar: debug mode, "verify citations" checkbox, API-key field (session memory only, never written to disk), model list.
Traces go to `logs/traces/<date>.jsonl`.

## Free-quota note
The runtime uses **free OpenRouter models only** (about 50 requests per day per account, reset at 00:00 UTC) and never falls back to a paid model. When the quota is exhausted or providers are congested, the UI shows a Ukrainian banner: paste another key in the sidebar or wait for the reset. Expect 10-70 s per answer on free models.

## Tests and lint
```bash
make test
make lint                   # ruff check + ruff format --check
```

## Evaluation
Gold sets are in `eval/data/review/` (unreviewed drafts). Details and results: `reports/report.md` section 5.

Zero-LLM evaluations:
```bash
uv run python -m eval.parse_eval --gold eval/data/review/parse_gold.jsonl
uv run python -m eval.figure_eval --gold eval/data/review/figure_gold.jsonl --no-judge
uv run python -m eval.retrieval_eval --gold eval/data/review/qa.jsonl [--skip-rerank]   # slow with the reranker on CPU
```

LLM components (use the free quota):
```bash
uv run python -m eval.run --component router --split dev --preset small
uv run python -m eval.run --component all --split dev --preset small
uv run python -m eval.report                      # rewrite reports/eval/summary.md
```
- `--preset small` samples a fixed-seed subset (router 20, answer 12 QA, unanswerable 5, logistics 5, verify 5) to fit one day's quota.
- Runs are resumable: finished items are stored in `reports/eval/runs/<run_id>/`. If the quota runs out, the run stops cleanly (exit code 2); re-run the same command after the reset or with another key in `.env`. The `run_id` hashes the models, prompt versions and pipeline flags, so changing a prompt starts a new run.
- `--split test` is for the frozen test files only; do not tune on it.

Judging is offline (no API): export tasks, have Claude Code Haiku agents judge them (skill `judge-batch`), then score:
```bash
uv run python -m eval.judge_tasks --run <RUN_ID> --component answer
# Haiku agents write reports/eval/runs/<RUN_ID>/judgments_*.jsonl
uv run python -m eval.score --component answer --run <RUN_ID> --write
uv run python -m eval.judge_tasks --run <RUN_ID> --component answer --calibration 20   # CSV for human calibration
```

## Layout
`app/ingest/` offline pipeline, `app/pipeline/` online components, `app/llm.py` the only LLM client, `prompts/` versioned prompts, `eval/` evaluations, `docs/` contracts, `reports/` report and results, `.claude/skills/` agent skills.
