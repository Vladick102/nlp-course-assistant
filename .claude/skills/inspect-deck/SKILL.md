---
name: inspect-deck
description: Inspect how one course PDF was parsed — compare extracted slides with rendered page images and report quirks. Use for [DU] review or parser debugging.
---
# inspect-deck
Args: `<doc_id> [pages]` (pages optional, e.g. `4,9,12`; default: 5 pages spread across the deck incl. 1 flagged needs_vision).

1. Look up the doc in `data/parsed/documents.json` (pdf_path, doc_type). If missing, run `uv run python -m app.ingest.run --only <doc_id>`.
2. **Delegate the visual comparison to a Haiku sub-agent** (AGENTS.md §8a). Brief it with: pdf_path, the page list,
   the matching records from `data/parsed/<doc_id>/slides.jsonl` (`jq -c 'select(.page_start==N)'`), and the render command
   `pdftoppm -r 80 -png -f P -l P <pdf> /tmp/inspect/x`. Ask for, per page: missing text, boilerplate leaked
   (nav bar, footer «Олег Фаренюк …», page numbers), wrong title, broken bullets/code, mojibake/latin-i, missed figure.
3. Summarise findings as a table and append new quirk types to `reports/review/<course>.md` (section "Follow-up inspections").
4. If a parser bug is confirmed: write a failing test in `tests/test_parser.py` first, then hand the fix to a Sonnet agent.
