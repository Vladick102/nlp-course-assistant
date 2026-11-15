"""[EVAL] Pure metric functions shared by all component evals (no I/O, no LLM)."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence

import numpy as np

# ------------------------------------------------------------------ text similarity


def tokens(text: str) -> list[str]:
    """Lowercased word tokens (unicode letters/digits; apostrophes kept inside words)."""
    return re.findall(r"\w+(?:['’]\w+)*", text.lower())


def token_f1(pred: str, gold: str) -> float:
    """Bag-of-words F1 between two strings (SQuAD style). Both empty → 1.0."""
    p, g = tokens(pred), tokens(gold)
    if not p and not g:
        return 1.0
    common = sum((Counter(p) & Counter(g)).values())
    if common == 0:
        return 0.0
    prec, rec = common / len(p), common / len(g)
    return 2 * prec * rec / (prec + rec)


def levenshtein(a: Sequence[Hashable], b: Sequence[Hashable]) -> int:
    """Edit distance (insert/delete/substitute = 1); O(len(a)*len(b)) time, O(len(b)) memory."""
    if len(a) < len(b):
        a, b = b, a
    prev = np.arange(len(b) + 1)
    for i, ca in enumerate(a, 1):
        cur = np.empty_like(prev)
        cur[0] = i
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return int(prev[-1])


def cer(pred: str, gold: str) -> float:
    """Character error rate = edit distance / len(gold). Empty gold: 0.0 if pred empty else 1.0."""
    if not gold:
        return 0.0 if not pred else 1.0
    return levenshtein(pred, gold) / len(gold)


# ------------------------------------------------------------------ ranking (binary relevance)


def _gold_set(gold: str | Iterable[str]) -> set[str]:
    return {gold} if isinstance(gold, str) else set(gold)


def recall_at_k(ranked: Sequence[str], gold: str | Iterable[str], k: int) -> float:
    """Share of gold ids found in the top-k (1.0 for a single gold id found, 0.0 otherwise)."""
    g = _gold_set(gold)
    return len(g & set(ranked[:k])) / len(g) if g else 0.0


def hit_at_k(ranked: Sequence[str], gold: str | Iterable[str], k: int) -> float:
    """1.0 if any gold id is in the top-k."""
    return float(bool(_gold_set(gold) & set(ranked[:k])))


def mrr_at_k(ranked: Sequence[str], gold: str | Iterable[str], k: int) -> float:
    """Reciprocal rank of the first gold id within the top-k, else 0."""
    g = _gold_set(gold)
    for i, r in enumerate(ranked[:k], 1):
        if r in g:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], gold: str | Iterable[str], k: int) -> float:
    """nDCG with binary gains; duplicates in `ranked` count once."""
    g = _gold_set(gold)
    if not g:
        return 0.0
    seen: set[str] = set()
    dcg = 0.0
    for i, r in enumerate(ranked[:k], 1):
        if r in g and r not in seen:
            dcg += 1 / math.log2(i + 1)
        seen.add(r)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(g), k) + 1))
    return dcg / ideal


# ------------------------------------------------------------------ classification


def per_class_prf(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None) -> dict:
    """{label: {precision, recall, f1, support}} plus a 'macro_f1' key."""
    labels = list(labels) if labels is not None else sorted(set(y_true) | set(y_pred))
    out: dict = {}
    for lab in labels:
        tp = sum(t == lab and p == lab for t, p in zip(y_true, y_pred, strict=True))
        fp = sum(t != lab and p == lab for t, p in zip(y_true, y_pred, strict=True))
        fn = sum(t == lab and p != lab for t, p in zip(y_true, y_pred, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    out["macro_f1"] = float(np.mean([out[lab]["f1"] for lab in labels])) if labels else 0.0
    return out


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None) -> float:
    return per_class_prf(y_true, y_pred, labels)["macro_f1"]


def accuracy(y_true: Sequence[object], y_pred: Sequence[object]) -> float:
    return float(np.mean([t == p for t, p in zip(y_true, y_pred, strict=True)])) if y_true else 0.0


def confusion(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None) -> np.ndarray:
    """Rows = gold, columns = predicted, in `labels` order."""
    labels = list(labels) if labels is not None else sorted(set(y_true) | set(y_pred))
    idx = {lab: i for i, lab in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred, strict=True):
        if t in idx and p in idx:
            m[idx[t], idx[p]] += 1
    return m


# ------------------------------------------------------------------ agreement / correlation


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    """Cohen's kappa for two raters (any hashable labels). Perfect chance-level agreement edge case → 1.0."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two equal-length, non-empty label lists")
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / n**2
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation (NaN when an input is constant)."""
    from scipy.stats import spearmanr

    return float(spearmanr(x, y).statistic)


# ------------------------------------------------------------------ uncertainty


def bootstrap_ci(
    values: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float, float]:
    """(point estimate, lo, hi) percentile bootstrap CI of `stat` over per-item `values`."""
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    boots = [stat(v[rng.integers(0, v.size, v.size)]) for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(stat(v)), float(lo), float(hi)
