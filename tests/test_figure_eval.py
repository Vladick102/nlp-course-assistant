from app.llm import LLMResult
from app.schemas import Slide
from eval import figure_eval as fe


def test_entity_found_substring_and_fuzzy():
    d = "Тип: діаграма. Блоки: Scheduler, Dispatcher та IRQ handler; стрілки від CPU."
    assert fe.entity_found("scheduler", d)
    assert fe.entity_found("Dispatchr", d)  # typo within the fuzzy threshold
    assert not fe.entity_found("Kernel", d)
    assert not fe.entity_found("", d)


def test_entity_recall():
    assert fe.entity_recall(["a", "b"], "тільки a тут") == 0.5
    assert fe.entity_recall(["a"], None) == 0.0
    assert fe.entity_recall([], None) == 1.0


def test_evaluate_with_mocks(monkeypatch):
    desc = Slide(doc_id="d", page_start=3, page_end=3, figure_description="Блоки CPU і MMU", body_md="x")
    bare = Slide(doc_id="d", page_start=4, page_end=4, body_md="y")
    monkeypatch.setattr(fe, "find_slide", lambda doc, page: {3: desc, 4: bare}.get(page))
    monkeypatch.setattr(fe.registry, "load", lambda: [type("D", (), {"doc_id": "d", "pdf_path": "p.pdf"})()])
    monkeypatch.setattr(fe, "page_png", lambda p, n: b"png")

    def fake_cj(prompt, role, **kw):
        assert role == "judge" and kw["images"] == [b"png"]
        return {"faithfulness": 9, "critical_hallucination": False, "reason": "ok"}, LLMResult("", "m", False, 0, {})

    monkeypatch.setattr(fe, "complete_json", fake_cj)
    items = [
        {"doc_id": "d", "page": 3, "entities": ["CPU", "MMU"], "takeaway": "t"},
        {"doc_id": "d", "page": 4, "entities": ["CPU"], "takeaway": "t"},
    ]
    res = fe.evaluate(items)
    assert res["n"] == 2 and res["n_judged"] == 1 and res["missing_description"] == 1
    assert res["items"][0]["faithfulness"] == 5  # clamped
    assert res["entity_recall"][0] == 0.5
    assert res["critical_hallucination_rate"] == 0.0
    assert "entity recall" in fe.markdown(res)
