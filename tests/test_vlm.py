from app.ingest import vlm
from app.llm import LLMResult
from app.schemas import Document, Slide


def test_is_decorative():
    assert vlm.is_decorative("ДЕКОРАТИВНЕ")
    assert vlm.is_decorative(" «ДЕКОРАТИВНЕ». ")
    assert not vlm.is_decorative("Тип: діаграма. Це не ДЕКОРАТИВНЕ зображення")


def test_apply_and_pending():
    s = Slide(doc_id="d", page_start=1, page_end=1, needs_vision=True, vision_reason="image 20%")
    assert vlm.pending([s]) == [s]
    dec = vlm.apply(s, "ДЕКОРАТИВНЕ")
    assert dec.figure_description is None and not dec.needs_vision and vlm.pending([dec]) == []
    ok = vlm.apply(s, "Тип: схема")
    assert ok.figure_description == "Тип: схема" and vlm.pending([ok]) == []


def test_describe_monkeypatched(monkeypatch):
    seen = {}

    def fake_complete(prompt, role, **kw):
        seen.update(role=role, **kw)
        return LLMResult("Тип: схема", "m", False, 0.0, {})

    monkeypatch.setattr(vlm, "complete", fake_complete)
    monkeypatch.setattr(vlm, "page_png", lambda pdf, page: b"png")
    doc = Document(
        doc_id="d", courses=["os"], doc_type="lecture", title="T {{x}}", source_files=[], pdf_path="x.pdf", n_pages=1
    )
    s = Slide(doc_id="d", page_start=1, page_end=1, title="Заг", body_md="текст", needs_vision=True)
    assert vlm.describe(doc, s) == "Тип: схема"
    assert seen["role"] == "vlm" and seen["images"] == [b"png"] and "{{" not in seen["doc_title"]
