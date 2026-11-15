import numpy as np
import pytest

from app.pipeline import retrieve
from app.schemas import Chunk


def test_rrf_math():
    out = dict(retrieve.rrf([["a", "b", "c"], ["b", "a"]], k=60))
    assert out["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert out["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert out["c"] == pytest.approx(1 / 63)
    ranked = [i for i, _ in retrieve.rrf([["x", "y"], ["y"]], k=60)]
    assert ranked == ["y", "x"]


def _chunk(cid, courses, kind="slide"):
    return Chunk(
        chunk_id=cid,
        doc_id="d",
        courses=courses,
        doc_type="lecture",
        kind=kind,
        breadcrumb="b",
        text="t",
        search_text="t",
    )


def test_course_filter_before_topk(monkeypatch):
    cs = {
        "a": _chunk("a", ["os"]),
        "b": _chunk("b", ["pok"]),
        "c": _chunk("c", ["pok", "os"]),
        "d": _chunk("d", ["os"], kind="logistics"),
    }
    ids = list(cs)
    monkeypatch.setattr(retrieve, "chunks", lambda: cs)
    monkeypatch.setattr(retrieve, "_dense", lambda: (np.array([[1.0], [0.9], [0.8], [0.7]], dtype=np.float32), ids))

    class FakeEmb:
        def encode(self, qs, normalize_embeddings=True):
            return np.array([[1.0]] * len(qs))

    monkeypatch.setattr(retrieve, "_embedder", lambda: FakeEmb())
    hits = retrieve.run(["q"], course="pok", k=2, mode="dense")
    assert [h.chunk_id for h in hits] == ["b", "c"]  # 'a' (best score) filtered out first
    hits = retrieve.run(["q"], course="os", k=5, mode="dense")
    assert [h.chunk_id for h in hits] == ["a", "c"]  # logistics excluded
    hits = retrieve.run(["q"], course="os", k=5, mode="dense", include_logistics=True)
    assert [h.chunk_id for h in hits] == ["a", "c", "d"]


def test_glossary_expansion():
    assert "process" in retrieve.expand_query("що таке процеси").lower()
    assert "кеш" in retrieve.expand_query("how does cache work")


def test_gold_matching_window_and_slide():
    from eval.retrieval_eval import item_metrics

    def ch(cid, kind, p0, p1):
        return Chunk(
            chunk_id=cid, doc_id="d", courses=["os"], doc_type="lecture", kind=kind, page_start=p0, page_end=p1,
            breadcrumb="b", text="t", search_text="t",
        )  # fmt: skip

    cs = {
        c.chunk_id: c
        for c in [
            ch("d#3", "slide", 3, 3),
            ch("d#4", "slide", 4, 4),
            ch("d#w3", "window", 3, 5),
            ch("d#9", "slide", 9, 9),
        ]
    }
    # gold slide d#4: window d#w3 covers it -> hit at rank 1
    m = item_metrics(["d#w3", "d#9"], ["d#4"], cs)
    assert m["R@1"] == 1.0 and m["MRR@10"] == 1.0
    # gold window d#w3: slide d#4 inside the window counts; d#9 does not
    m = item_metrics(["d#9", "d#4"], ["d#w3"], cs)
    assert m["R@1"] == 0.0 and m["R@5"] == 1.0 and m["MRR@10"] == 0.5
    assert item_metrics(["d#9"], ["d#4"], cs)["R@10"] == 0.0


def test_rerank_knobs(monkeypatch):
    from app.pipeline import rerank
    from app.schemas import Hit

    seen = {}

    class FakeCE:
        def predict(self, pairs, **kw):
            seen["n"] = len(pairs)
            seen["max_chars"] = max(len(p[1]) for p in pairs)
            return np.arange(len(pairs), dtype=float)

    cs = {f"c{i}": _chunk(f"c{i}", ["os"]).model_copy(update={"search_text": "x" * 5000}) for i in range(6)}
    monkeypatch.setattr(rerank, "chunks", lambda: cs)
    monkeypatch.setattr(rerank, "_model", lambda name, ml: FakeCE())
    hits = [Hit(chunk_id=f"c{i}", score=1.0, rank=i + 1, source="rrf") for i in range(6)]
    out = rerank.run("q", hits, k=2, candidates=4, max_length=128)
    assert seen["n"] == 4 and seen["max_chars"] == 512
    assert [h.chunk_id for h in out] == ["c3", "c2"] and out[0].score > out[1].score
