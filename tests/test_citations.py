"""Citation tag parsing and answer building (no LLM, fake store)."""

from __future__ import annotations

import pytest

from app import store
from app.pipeline import generate, verify
from app.schemas import Chunk, Document


def _chunk(cid: str, doc: str, page: int | None, courses=("os",), title="Процеси", end: int | None = None) -> Chunk:
    return Chunk(
        chunk_id=cid,
        doc_id=doc,
        courses=list(courses),
        doc_type="lecture",
        page_start=page,
        page_end=end if end is not None else page,
        title=title,
        breadcrumb=f"ОС > {title}",
        text=f"text of {cid}",
        search_text=f"text of {cid}",
        urls=["https://example.com/x"] if page == 12 else [],
    )


@pytest.fixture
def chunks(monkeypatch) -> list[Chunk]:
    cs = [
        _chunk("os_l010#12", "os_l010", 12),
        _chunk("os_l010#13", "os_l010", 13, end=14),
        _chunk("os_l010#summary", "os_l010", None, title="Огляд"),
    ]
    doc = Document(
        doc_id="os_l010",
        courses=["os"],
        doc_type="lecture",
        title="Процеси та потоки",
        source_files=[],
        pdf_path="x.pdf",
        n_pages=30,
    )
    monkeypatch.setattr(store, "documents", lambda: {"os_l010": doc})
    monkeypatch.setattr(store, "chunks", lambda: {c.chunk_id: c for c in cs})
    return cs


def test_valid_tags_and_label(chunks):
    text, cites, invalid = generate.parse_citations("Процес - це програма у виконанні. [S1] Потік легший [S2].", chunks)
    assert text == "Процес - це програма у виконанні. [S1] Потік легший [S2]."
    assert invalid == []
    assert [c.chunk_id for c in cites] == ["os_l010#12", "os_l010#13"]
    assert cites[0].label == "ОС · Процеси та потоки · сл. 12"
    assert cites[1].label == "ОС · Процеси та потоки · сл. 13–14"
    assert cites[0].urls == ["https://example.com/x"]


def test_summary_label_has_no_slide_number(chunks):
    _, cites, _ = generate.parse_citations("Огляд. [S3]", chunks)
    assert cites[0].label == "ОС · Процеси та потоки"


def test_unknown_tags_removed_and_reported(chunks):
    text, cites, invalid = generate.parse_citations("Факт [S1][S9]. Інше [S7].", chunks)
    assert text == "Факт [S1]. Інше."
    assert invalid == ["S9", "S7"]
    assert len(cites) == 1


def test_zero_tag_is_invalid(chunks):
    _, _, invalid = generate.parse_citations("Факт [S0].", chunks)
    assert invalid == ["S0"]


def test_adjacent_tags(chunks):
    text, cites, invalid = generate.parse_citations("Факт [S1][S3].", chunks)
    assert text == "Факт [S1][S3]."
    assert [c.chunk_id for c in cites] == ["os_l010#12", "os_l010#summary"]
    assert invalid == []


def test_comma_list_is_normalised(chunks):
    text, cites, _ = generate.parse_citations("Факт [S1, S2].", chunks)
    assert text == "Факт [S1][S2]."
    assert len(cites) == 2


def test_comma_list_with_unknown(chunks):
    text, cites, invalid = generate.parse_citations("Факт [S2, S5].", chunks)
    assert text == "Факт [S2]."
    assert invalid == ["S5"]
    assert [c.chunk_id for c in cites] == ["os_l010#13"]


def test_range_expands(chunks):
    text, cites, invalid = generate.parse_citations("Факт [S1-S3].", chunks)
    assert text == "Факт [S1][S2][S3]."
    assert len(cites) == 3 and invalid == []


def test_citations_ordered_by_first_use_and_deduped(chunks):
    _, cites, _ = generate.parse_citations("A [S2]. B [S1]. C [S2][S1].", chunks)
    assert [c.chunk_id for c in cites] == ["os_l010#13", "os_l010#12"]


def test_non_tag_brackets_untouched(chunks):
    text, cites, invalid = generate.parse_citations("Масив a[1] і [Sx] залишаються. [S1]", chunks)
    assert "a[1]" in text and "[Sx]" in text
    assert len(cites) == 1 and invalid == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("У матеріалах курсу цього немає.", True),
        ("  у матеріалах курсу цього немає [S1]", True),
        ("Процес - це... У матеріалах курсу цього немає.", False),
        ("Звичайна відповідь [S1].", False),
    ],
)
def test_is_abstain(raw, expected):
    assert generate.is_abstain(raw) is expected


def test_build_answer_abstain_points_to_slides(chunks):
    ans = generate.build_answer("content", "У матеріалах курсу цього немає.", chunks)
    assert ans.abstained
    assert ans.text.startswith("У матеріалах курсу цього немає.")
    assert 1 <= len(ans.citations) <= 3
    assert ans.citations[0].label in ans.text


def test_build_answer_normal(chunks):
    ans = generate.build_answer("content", "Так [S1][S8].", chunks)
    assert not ans.abstained
    assert ans.invalid_citations == ["S8"]
    assert ans.debug["tag_map"]["S1"] == "os_l010#12"


def test_split_sentences_glues_tag_fragments():
    s = verify.split_sentences("Перше речення. [S1] Друге [S2].\n- пункт списку [S1]")
    assert s == ["Перше речення. [S1]", "Друге [S2].", "- пункт списку [S1]"]
