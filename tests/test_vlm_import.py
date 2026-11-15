import json

import pytest

from app.ingest import run as ingest_run
from app.ingest import vlm, vlm_import
from app.schemas import Document, Slide

GOOD = "Тип: схема\nЕлементи та зв'язки: A -> B\nВисновок: A керує B\nПідписи: A | B"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_run, "path", lambda name: tmp_path / name)
    doc = Document(
        doc_id="d1", courses=["os"], doc_type="lecture", title="T", source_files=[], pdf_path="x.pdf", n_pages=9
    )
    slides = [
        Slide(doc_id="d1", page_start=1, page_end=1, needs_vision=True, vision_reason="img"),
        Slide(doc_id="d1", page_start=2, page_end=4, needs_vision=True, vision_reason="img"),
        Slide(doc_id="d1", page_start=5, page_end=5, needs_vision=True, vision_reason="img"),
        Slide(doc_id="d1", page_start=6, page_end=6),
    ]
    ingest_run.save_slides(doc, slides)
    out = tmp_path / "out"
    out.mkdir()

    def write(lines: list, tail: str = ""):
        body = "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n" + tail
        (out / "b.jsonl").write_text(body, encoding="utf-8")

    def go():
        return vlm_import.run([out], quiet=True, docs=[doc])

    return write, go, tmp_path


def test_page_matching_and_decorative(env):
    write, go, _ = env
    write(
        [
            {"doc_id": "d1", "page": 4, "description": GOOD},
            {"doc_id": "d1", "page": 1, "description": "ДЕКОРАТИВНЕ"},
            {"doc_id": "d1", "page": 99, "description": GOOD},
            {"doc_id": "zz", "page": 1, "description": GOOD},
        ]
    )
    st = go()
    by = {s.page_start: s for s in ingest_run.load_slides("d1")}
    assert by[2].figure_description == GOOD and by[2].needs_vision
    assert by[1].figure_description is None and not by[1].needs_vision and by[1].vision_reason == vlm.DECORATIVE
    assert by[5].figure_description is None
    assert (st["imported"], st["decorative"], st["unmatched"], st["malformed"]) == (1, 1, 2, 0)
    assert st["coverage"]["done"] == 2 and st["coverage"]["flagged"] == 3


def test_malformed_still_imported(env):
    write, go, _ = env
    write([{"doc_id": "d1", "page": 5, "description": "  просто текст  "}])
    st = go()
    assert st["malformed"] == 1 and st["imported"] == 1
    assert ingest_run.load_slides("d1")[2].figure_description == "просто текст"


def test_truncated_last_line_and_idempotent(env):
    write, go, tmp = env
    write([{"doc_id": "d1", "page": 2, "description": GOOD}], tail='{"doc_id": "d1", "pa')
    st = go()
    assert st["lines"] == 1
    first = ingest_run.slides_file("d1").read_bytes()
    st2 = go()
    assert ingest_run.slides_file("d1").read_bytes() == first
    assert st2["coverage"] == st["coverage"]
