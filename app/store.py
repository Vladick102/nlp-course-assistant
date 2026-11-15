"""Cached loaders for parsed/indexed artifacts."""

from __future__ import annotations

import json
from functools import cache

from app.config import path
from app.schemas import Chunk, Document


@cache
def chunks() -> dict[str, Chunk]:
    with open(path("index") / "chunks.jsonl", encoding="utf-8") as f:
        return {c.chunk_id: c for c in (Chunk(**json.loads(ln)) for ln in f)}


@cache
def documents() -> dict[str, Document]:
    with open(path("parsed") / "documents.json", encoding="utf-8") as f:
        return {d["doc_id"]: Document(**d) for d in json.load(f)}


@cache
def catalog() -> list[dict]:
    with open(path("index") / "catalog.json", encoding="utf-8") as f:
        return json.load(f)
