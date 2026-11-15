# Agent log — how the coding agents were steered

Format: date · what context/brief was given · what went wrong or was learned · rule added (where).

- 2026-11-15 · Planning. PLAN.md written before any code; open questions answered by the user (syllabus as the logistics
  source, OpenRouter only, Streamlit, strictly grounded answers) → frozen as "Fixed decisions" in AGENTS.md §2.
- 2026-11-15 · Data understanding delegated to 3 Haiku agents (one per course folder), each brief asked for a
  file-per-section report in `reports/review/` and "facts only, say *not checked* rather than guess". Result: they found
  issues the sample deck in PLAN.md §0 did not show — cp1251 mojibake in ~10 decks, Latin "i" in Ukrainian words,
  student/third-party decks, superseded requirements deck, three conflicting grading schemes. → `data/doc_overrides.yaml`
  (curated registry) and `app/ingest/textnorm.py`; rule "Raw folders read-only" in AGENTS.md §2.
- 2026-11-15 · Orchestrator wrote the first parser itself; the user then asked for delegation: **Haiku for PDF analysis,
  Sonnet for code**. → AGENTS.md §8a (multi-agent workflow, file ownership), `docs/interfaces.md` (contract so parallel
  Sonnet agents can build disjoint modules), skills reference Haiku for page inspection.
- 2026-11-15 · Gold labels drafted by a Haiku agent from page *images* (not from parser output, to avoid circular
  evaluation) into `eval/data/review/` — human review required before promotion (AGENTS.md §7).
- 2026-11-15 · VLM model comparison delegated to a Haiku agent with a hard budget stop ($5 projected). It stopped correctly
  on HTTP 402 (OpenRouter account had no purchased credits, free tier) instead of retrying. But 1 of its 2 "bugs found
  elsewhere" was false (claimed a missing `import argparse` that exists). → Orchestrator rule: verify sub-agent claims
  about files they don't own before acting on them; cheap agents are fine for execution, not for unverified diagnosis.
- 2026-11-15 · Runtime model chosen under a hard constraint (user: strictly free, no paid fallback). Orchestrator ran a
  6-model free smoke test (router JSON + grounded fork/exec answer): ling-3.2-flash 21 s ✓, nemotron-3-ultra 70 s ✓,
  gemma-4-31b/26b 429 (provider congestion), nemotron-3.5 lightning/super-vl empty output (reasoning ate max_tokens).
  → `min_max_tokens` in config; merged router+rewrite to halve calls; quota-aware errors + UI banner; AGENTS.md §2 rule
  "never a paid fallback" and "cap live calls in every brief" (free quota ≈ 50 req/day).
- 2026-11-15 · Figure descriptions: orchestrator first launched batch workers itself (24 batches); the user asked to let a
  simpler model do the dispatching. → Haiku coordinator agent for batches 24–41 (dispatch, ≤6 concurrent, verify, retry,
  import) with a hard "stop if you can't spawn sub-agents" guard; rule added to AGENTS.md §8a ("Bulk jobs").
  Side finding: workers saw `<<ccr:…>>` placeholders = harness-abbreviated tool output, not data — brief now says
  "read input one record at a time".
- 2026-11-15 · Report writing delegated to Sonnet: the harness blocks sub-agents from writing report files ("return
  findings as text"); the agent correctly refused to bypass it via Bash. → Pattern: writing agents return the document
  as text, the orchestrator saves it verbatim. Also caught by the agent: stale counts in the brief (docs/chunks changed
  after re-index) → rule: briefs cite files, not remembered numbers.
