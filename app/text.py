"""Tokenisation + lemmatisation shared by the indexer and the BM25 query side."""

from __future__ import annotations

import re
from functools import lru_cache

import pymorphy3

TOKEN_RE = re.compile(r"[^\W_]+(?:[_'’ʼ][^\W_]+)*(?:\+\+|#)?", re.UNICODE)
CYR_RE = re.compile(r"[а-щьюяіїєґ]", re.I)

STOPWORDS = frozenset(
    """
    і й та а але або чи що як це цей ця ці той та те ті в у на з із зі до від по за про для при під над між
    не ні би б же ж то так також ще вже тільки лише бути є був була було були буде можна який яка яке які
    його її їх їм він вона воно вони ми ви я ти свій наш ваш де коли тут там якщо тоді адже щоб
    the a an of to in on for and or is are was were be by with as at it this that from
    """.split()  # noqa: SIM905
)


@lru_cache(maxsize=1)
def _morph() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer(lang="uk")


@lru_cache(maxsize=200_000)
def _lemma(tok: str) -> str:
    if CYR_RE.search(tok):
        return _morph().parse(tok)[0].normal_form
    return tok


def lemmas(text: str) -> list[str]:
    out: list[str] = []
    for raw in TOKEN_RE.findall(text.lower().replace("’", "'").replace("ʼ", "'")):
        parts = [raw]
        if "_" in raw:  # MPI_Send -> mpi_send, mpi, send
            parts += raw.split("_")
        for p in parts:
            lem = _lemma(p)
            if lem not in STOPWORDS and (len(lem) > 1 or lem.isdigit()):
                out.append(lem)
    return out
