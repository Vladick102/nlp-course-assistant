# AGENTS.md — rules for coding agents working in this repo

`CLAUDE.md` is a symlink to this file. **`PLAN.md` is the source of truth for design**; this file is the
source of truth for *how* to work. If they conflict, stop and ask.

## 1. Project in one paragraph
Course Assistant: a Streamlit chat app that answers Ukrainian students' questions about three courses
(**pok** = ПОК, **aks** = АКС, **os** = ОС) strictly from the course materials (lecture PDFs/PPTX, labs,
syllabi). Pipeline: guard → LLM router → (content: rewrite → hybrid BM25+dense retrieval → rerank →
sufficiency gate → grounded answer with slide citations → citation verifier) | logistics (syllabus) |
navigation (catalog) | clarify | off_topic. Every component is evaluated in isolation (PLAN.md §6).

## 2. Fixed decisions (do not re-open)
- LLM provider for the **running app**: OpenAI-compatible API via `app/llm.py`; model IDs live **only** in `config.yaml`.
  The OpenRouter account has **no paid balance** (user decision, 2026-11-15) — don't plan on paid OpenRouter calls.
- **Runtime is strictly FREE models** (`:free` suffix). **Never add a paid model as a fallback.** When the free quota is
  exhausted or providers are congested, the app must say so (Ukrainian banner: change the API key or wait for reset)
  instead of silently switching to a paid model. Free daily quota is ~50 requests: cap live test calls in every brief.
- **Offline LLM work** (figure descriptions, gold-label drafting, LLM-as-judge) is done by **Claude Code Haiku
  sub-agents**, not API calls. Their outputs are saved as tracked files (`data/figure_descriptions/`, `eval/data/review/`,
  `reports/eval/runs/<run_id>/judgments_*.jsonl`) so the pipeline is reproducible without re-running them.
  Blindness rules: figure describers never see figure gold; gold builders never see system outputs; judges DO see the
  reference answer/key facts (needed to score correctness) but never the gold chunk ids or other systems' scores.
- UI: **Streamlit**.
- Answers are **strictly grounded in course materials**. No general-knowledge fallback. If the material does
  not support an answer → abstain with «У матеріалах курсу цього немає» + closest slides.
- Logistics (grading, deadlines, tools, prerequisites) is answered **from the syllabi / requirements decks**
  only, with the source document cited.
- Raw data lives in `pok/`, `aks/`, `os/` at repo root. **Read-only. Never move, rename, edit or delete.**

## 3. CRISP-DM workflow (mandatory)
Every task you take on belongs to exactly one phase. State it in your first message for the task:
`[BU]` business understanding, `[DU]` data understanding, `[DP]` data preparation, `[MOD]` modeling,
`[EVAL]` evaluation, `[DEP]` deployment.
- `[DU]` findings go into `reports/data_inventory.md` or `reports/review/*.md`, **not only into chat**.
- `[MOD]` changes that can move a metric: run the component eval **before and after**, and append one row to
  `reports/eval/history.md` (`date | component | change | metric before → after | kept?`).
  Use the `run-eval` skill.
- `[EVAL]` never tune on the test split. Thresholds, prompts and few-shots are tuned on `dev` only.
- If a metric is below its target in PLAN.md §1.4, use the `error-analysis` skill before changing code.

## 4. Code conventions
- Python 3.12, deps via `uv add` (never pip). Run things with `uv run ...`.
- Type hints everywhere. Pydantic models from `app/schemas.py` at every component boundary.
- **One component = one module with a pure-ish `run(...)` entry point** that can be called from
  `eval/` without the UI. No Streamlit imports outside `app/ui.py`.
- `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` must pass before you say "done".
- Prefer small, readable code over frameworks (no LangChain/LlamaIndex). Don't add abstractions that have one user.
- Paths and thresholds come from `config.yaml` via `app/config.py`; no magic constants inside components.

## 5. LLM rules
- **All** LLM/VLM calls go through `app/llm.py` (disk cache + retries + JSONL trace). Never instantiate a client elsewhere.
- Prompts live in `prompts/<name>.md` with a `version:` front-matter line. Never inline prompts in Python.
  Changing a prompt's wording ⇒ bump its version (cache key and traces include it).
- Structured outputs: ask for JSON, validate with pydantic, on failure retry once then fall back (documented per component).
- Judge model ≠ generator model (see `config.yaml`).
- Never commit `.env` or keys. Never print keys.

## 6. Language rules
- User-facing text (UI, answers, abstain/reject templates): **Ukrainian**.
- Code, comments, docs, reports, commit messages: **English**.
- Keep English technical terms as-is inside Ukrainian answers (MMU, fork(), POSIX).

## 7. Data and eval-data rules
- Generated artifacts (`data/converted`, `data/parsed`, `data/index`, `data/cache`, `logs/`) must be
  reproducible from `make` targets / scripts; they are git-ignored.
- Gold data in `eval/data/`. Files containing `test` are **frozen**: never regenerate, edit or "fix" them to
  raise a score. New items go to `eval/data/review/*.jsonl` first (skill `add-gold-items`) and are promoted by a human.
- When you report a metric, report the split, the n, and the prompt versions.

## 8. Context hygiene (what to read first)
| Task | Read first | Do NOT read |
|---|---|---|
| Parser / ingest | `app/ingest/parser.py`, `tests/test_parser.py`, `reports/review/*.md`, one `data/parsed/<deck>/<deck>.md` | raw PDFs in full (render single pages instead; use skill `inspect-deck`) |
| Retrieval | `app/pipeline/retrieve.py`, `rerank.py`, `eval/metrics.py`, last rows of `reports/eval/history.md` | `data/index/*` (binary), `data/cache/*` |
| Prompts / generation | `prompts/<name>.md`, the component module, failing items from the last eval JSON | full traces dir — use skill `trace-debug` for one trace |
| Report | `reports/eval/summary.md`, `reports/eval/history.md`, `PLAN.md` | code |
- Large PDFs: delegate page-by-page reading to a cheap sub-agent (Haiku) and ask for a written summary file.
- Do not paste whole JSONL files into context; use `jq`/`head` with filters.

## 8a. Multi-agent workflow (who does what)
- **Orchestrator** (main session): plans, writes briefs, owns `AGENTS.md`/`PLAN.md`/skills, reviews diffs, runs checks.
- **Haiku sub-agents**: all PDF reading/analysis (data review, gold-label drafting from page images). Output → files.
- **Sonnet sub-agents**: code writing. Each brief names the files the agent **owns** (no edits outside them),
  the interfaces from `docs/interfaces.md` it must implement/consume, and the tests that must pass.
- **Bulk jobs** (many identical batches): the orchestrator writes one worker prompt and hands dispatch + verification to a
  **Haiku coordinator** (launches workers, ≤6 concurrent, checks line counts/JSON, retries once, runs the importer).
  The orchestrator only reads the coordinator's final summary — keeps the expensive context small.
- Parallel agents never own the same file. Interface changes go through the orchestrator (update `docs/interfaces.md` first).

## 9. Definition of done
1. ruff + pytest green. 2. Component eval runs and its numbers are in `reports/eval/history.md`.
3. README updated if a command/CLI changed. 4. Short note in `reports/agent_log.md` if an agent mistake led
to a new rule here (what went wrong → rule added).

## 10. Skills (`.claude/skills/`)
`inspect-deck`, `run-eval`, `error-analysis`, `add-gold-items`, `prompt-iteration`, `trace-debug`,
`crisp-dm-report`. Use them instead of ad-hoc procedures.
