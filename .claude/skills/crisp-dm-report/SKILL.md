---
name: crisp-dm-report
description: Update reports/report.md (final submission report) from the current eval summary, history, data inventory and diagrams.
---
# crisp-dm-report
1. Inputs: `PLAN.md`, `reports/data_inventory.md`, `reports/eval/summary.md`, `reports/eval/history.md`,
   latest `reports/eval/error_analysis_*.md`, `docs/interfaces.md`, `reports/agent_log.md`.
2. Report structure (one section per CRISP-DM phase): Business understanding (scope, use cases, business rules kept) →
   Data understanding (inventory numbers, quirks) → Data preparation (ingest diagram) → Modeling (mermaid data-flow
   diagram, component table: purpose/input/output/model or tool calls) → Evaluation (per-component metric tables vs targets,
   ablations, judge calibration, error analysis and why scores aren't higher) → Deployment (how to run) →
   Agentic development (AGENTS.md, skills, sub-agent delegation, lessons from agent_log).
3. Numbers must be copied from result files, with split, n and prompt versions. Never invent or round up.
4. Render the mermaid diagram to PNG if `mmdc` is available; otherwise keep mermaid source.
