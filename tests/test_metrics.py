import math

import numpy as np
import pytest

from eval import metrics as m


def test_token_f1():
    assert m.token_f1("a b c", "a b c") == 1.0
    assert m.token_f1("", "") == 1.0
    assert m.token_f1("a", "") == 0.0
    assert m.token_f1("a b", "c d") == 0.0
    assert m.token_f1("a b c d", "a b") == pytest.approx(2 * 0.5 * 1 / 1.5)
    assert m.token_f1("Процеси, ПОТОКИ", "процеси потоки") == 1.0
    assert m.token_f1("a a b", "a b b") == pytest.approx(2 / 3)


def test_levenshtein_and_cer():
    assert m.levenshtein("kitten", "sitting") == 3
    assert m.levenshtein("", "abc") == 3
    assert m.levenshtein("abc", "abc") == 0
    assert m.cer("abcd", "abcd") == 0.0
    assert m.cer("abxd", "abcd") == 0.25
    assert m.cer("", "abcd") == 1.0
    assert m.cer("", "") == 0.0 and m.cer("x", "") == 1.0
    assert m.cer("процес", "процеси") == pytest.approx(1 / 7)


def test_recall_hit_mrr():
    r = ["a", "b", "c", "d"]
    assert m.recall_at_k(r, "c", 2) == 0.0 and m.recall_at_k(r, "c", 3) == 1.0
    assert m.recall_at_k(r, {"a", "d", "z"}, 4) == pytest.approx(2 / 3)
    assert m.hit_at_k(r, {"z", "b"}, 1) == 0.0 and m.hit_at_k(r, {"z", "b"}, 2) == 1.0
    assert m.mrr_at_k(r, "c", 10) == pytest.approx(1 / 3)
    assert m.mrr_at_k(r, {"d", "b"}, 10) == 0.5
    assert m.mrr_at_k(r, "c", 2) == 0.0
    assert m.recall_at_k(r, set(), 3) == 0.0


def test_ndcg():
    assert m.ndcg_at_k(["a", "b"], "a", 5) == 1.0
    assert m.ndcg_at_k(["x", "a"], "a", 5) == pytest.approx(1 / math.log2(3))
    assert m.ndcg_at_k(["a", "x", "b"], {"a", "b"}, 3) == pytest.approx((1 + 0.5) / (1 + 1 / math.log2(3)))
    assert m.ndcg_at_k(["x", "y"], "a", 5) == 0.0
    assert m.ndcg_at_k(["a", "a"], "a", 5) == 1.0  # duplicates do not inflate


def test_classification():
    yt = ["a", "a", "b", "b", "c"]
    yp = ["a", "b", "b", "b", "a"]
    prf = m.per_class_prf(yt, yp)
    assert prf["a"]["precision"] == 0.5 and prf["a"]["recall"] == 0.5
    assert prf["b"]["precision"] == pytest.approx(2 / 3) and prf["b"]["recall"] == 1.0
    assert prf["c"]["f1"] == 0.0 and prf["c"]["support"] == 1
    assert m.macro_f1(yt, yp) == pytest.approx((0.5 + 0.8 + 0.0) / 3)
    assert m.accuracy(yt, yp) == 0.6
    cm = m.confusion(yt, yp, labels=["a", "b", "c"])
    assert cm.tolist() == [[1, 1, 0], [0, 2, 0], [1, 0, 0]]
    from sklearn.metrics import f1_score

    assert m.macro_f1(yt, yp) == pytest.approx(f1_score(yt, yp, average="macro", zero_division=0))


def test_kappa_spearman():
    assert m.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert m.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0.0
    assert m.cohen_kappa(["y", "y", "n", "y"], ["y", "n", "n", "y"]) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        m.cohen_kappa([], [])
    assert m.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert m.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)


def test_bootstrap_ci():
    est, lo, hi = m.bootstrap_ci([1, 0, 1, 1, 0, 1, 1, 1, 0, 1], n_boot=500)
    assert est == pytest.approx(0.7) and lo <= est <= hi and lo >= 0 and hi <= 1
    assert m.bootstrap_ci([1.0] * 5) == (1.0, 1.0, 1.0)
    assert math.isnan(m.bootstrap_ci([])[0])
    assert m.bootstrap_ci([1, 2, 3, 4, 100], stat=np.median, n_boot=200)[0] == 3.0
    assert m.bootstrap_ci([1, 0, 1, 0], seed=1) == m.bootstrap_ci([1, 0, 1, 0], seed=1)
