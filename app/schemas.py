"""Pydantic models exchanged between components."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["lecture", "lab", "logistics", "other"]
Route = Literal["content", "logistics", "navigation", "clarify", "off_topic"]


class Document(BaseModel):
    doc_id: str  # e.g. "os_l010_processes"; unique across courses
    courses: list[str]  # a deck can belong to several courses
    doc_type: DocType
    title: str
    source_files: list[str]  # repo-relative paths of the raw file(s)
    pdf_path: str  # repo-relative path to the PDF used for parsing/rendering
    n_pages: int
    order: float = 999.0  # lecture order inside the course (from filename), 999 = unknown


class Slide(BaseModel):
    doc_id: str
    page_start: int  # 1-based, as printed in PDF viewers
    page_end: int
    section: str | None = None
    title: str | None = None
    body_md: str = ""
    footnotes: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    needs_vision: bool = False
    vision_reason: str | None = None
    figure_description: str | None = None

    @property
    def slide_id(self) -> str:
        return f"{self.doc_id}#{self.page_start}"


class Chunk(BaseModel):
    chunk_id: str  # "<doc_id>#<page_start>" or "<doc_id>#summary" or "<doc_id>#w<p>"
    doc_id: str
    courses: list[str]
    doc_type: DocType
    kind: Literal["slide", "window", "summary", "logistics"] = "slide"
    page_start: int | None = None
    page_end: int | None = None
    title: str | None = None
    breadcrumb: str
    text: str  # text shown to the generator
    search_text: str  # text indexed by BM25 / embeddings (breadcrumb + text)
    urls: list[str] = Field(default_factory=list)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class GuardResult(BaseModel):
    text: str
    ok: bool
    flags: list[str] = Field(default_factory=list)
    reply: str | None = None  # canned reply if not ok


class RouteDecision(BaseModel):
    route: Route
    course: Literal["pok", "aks", "os"] | None = None
    confidence: float = 0.5
    reason: str = ""
    queries: list[str] = Field(default_factory=list)  # filled by the merged route+rewrite prompt


class Rewrite(BaseModel):
    queries: list[str]
    course: Literal["pok", "aks", "os"] | None = None


class Hit(BaseModel):
    chunk_id: str
    score: float
    rank: int
    source: str = ""  # bm25 / dense / rrf / rerank


class GateDecision(BaseModel):
    sufficient: bool
    top_score: float
    method: Literal["threshold", "llm"]
    reason: str = ""


class Citation(BaseModel):
    tag: str = ""  # "S1" — the inline tag the generator used for this source
    chunk_id: str
    doc_id: str
    page_start: int | None
    page_end: int | None
    label: str  # human label, e.g. "ОС · os_l010_processes · сл. 12"
    title: str | None = None
    urls: list[str] = Field(default_factory=list)


class VerifyResult(BaseModel):
    supported: bool
    unsupported_sentences: list[str] = Field(default_factory=list)
    bad_citations: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    route: Route
    text: str
    citations: list[Citation] = Field(default_factory=list)
    abstained: bool = False
    invalid_citations: list[str] = Field(default_factory=list)
    trace_id: str = ""
    debug: dict = Field(default_factory=dict)
