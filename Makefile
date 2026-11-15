.PHONY: convert ingest vlm index all test lint ui eval-retrieval

convert:
	uv run python -m app.ingest.convert

ingest:
	uv run python -m app.ingest.run

vlm:
	uv run python -m app.ingest.vlm

index:
	uv run python -m app.ingest.chunker
	uv run python -m app.ingest.catalog
	uv run python -m app.ingest.indexer

all: convert ingest vlm index

# GOLD=eval/data/review/qa.jsonl until eval/data/qa_dev.jsonl exists
eval-retrieval:
	uv run python -m eval.retrieval_eval $(if $(GOLD),--gold $(GOLD),)

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

ui:
	PYTHONPATH=. uv run streamlit run app/ui.py
