# Component interfaces (contract between modules)

All models are in `app/schemas.py`. Config via `app.config.cfg()` / `path()`. LLM calls only via `app/llm.py`
(`load_prompt`, `complete`, `complete_json`, `new_trace`, `trace_event`).

## Offline (ingest) — already implemented unless noted
| Module | Entry point | Output |
|---|---|---|
| `app/ingest/convert.py` | `run()` | `data/converted/<course>/*.pdf` |
| `app/ingest/registry.py` | `build() -> list[Document]`, `load()` | `data/parsed/documents.json` |
| `app/ingest/parser.py` | `parse_pdf(pdf, doc_id) -> list[Slide]` | — |
| `app/ingest/figures.py` | `flag_slides(pdf, slides)`, `page_png(pdf_path, page_no) -> bytes` | — |
| `app/ingest/run.py` | `main()`, `load_slides(doc_id)`, `save_slides(doc, slides)` | `data/parsed/<doc_id>/slides.jsonl`, `.md` |
| `app/ingest/vlm.py` *(todo)* | `run(limit=None)` | fills `Slide.figure_description` in slides.jsonl |
| `app/ingest/chunker.py` *(todo)* | `build() -> list[Chunk]` | `data/index/chunks.jsonl` |
| `app/ingest/indexer.py` *(todo)* | `build()` | `data/index/{bm25.pkl, dense.npy, chunk_ids.json}` |
| `app/ingest/catalog.py` *(todo)* | `build()` | `data/index/catalog.json` (doc → title, courses, order, slide titles, summary) |

## Online (pipeline) — every module exposes `run(...)`
| Module | Signature |
|---|---|
| `app/store.py` | `chunks() -> dict[str, Chunk]`, `documents() -> dict[str, Document]`, `catalog() -> list[dict]` (cached) |
| `app/text.py` | `lemmas(text) -> list[str]` (pymorphy3 uk + lowercase EN; shared by indexer and BM25 query side) |
| `guard.py` | `run(text: str) -> GuardResult` |
| `router.py` | `run(question: str, history: list[Turn], flags: list[str] = []) -> RouteDecision` |
| `rewrite.py` | `run(question: str, history: list[Turn], course: str|None) -> Rewrite` |
| `retrieve.py` | `run(queries: list[str], course: str|None, k: int|None=None, mode="hybrid") -> list[Hit]` (mode: bm25/dense/hybrid) |
| `rerank.py` | `run(query: str, hits: list[Hit], k: int|None=None) -> list[Hit]` (scores = sigmoid cross-encoder, 0..1) |
| `gate.py` | `run(question: str, hits: list[Hit]) -> GateDecision` |
| `generate.py` | `run(question: str, history: list[Turn], hits: list[Hit], fix: list[str] = []) -> Answer` (fix = sentences to remove/fix on regeneration) |
| `verify.py` | `run(answer: Answer, hits: list[Hit], chunks=None) -> VerifyResult` |
| `logistics.py` | `run(question: str, history: list[Turn], course: str|None) -> Answer` |
| `navigate.py` | `run(question: str, course: str|None) -> Answer` |
| `app/pipeline/answer.py` | `run(question: str, history: list[Turn]) -> Answer` — orchestrates all of the above, one trace per call, `Answer.debug` holds route, queries, hits+scores, gate, verify, timings |

## Citation format
Generator sees chunks labelled `[S1]..[Sk]`; it cites with these tags. `generate.py` maps tags → `Citation`
(`label` like «ОС · Процеси та потоки · сл. 12»), strips unknown tags into `Answer.invalid_citations`.
UI renders citations as links to the slide image.

## Catalog entry (`data/index/catalog.json`, list)
`{doc_id, title, courses, doc_type, order, n_slides, slide_titles: [{page, title}], summary: str|null}`

## Citation ↔ inline tag
`Citation.tag` holds the generator's tag ("S1"); UI replaces `[S1]` in `Answer.text` with a link to that citation.
