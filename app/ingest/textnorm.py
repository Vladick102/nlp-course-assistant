"""[DP] Text normalization shared by the parser and the indexer.

Fixes found in data understanding (reports/review/*.md):
  * Latin 'i'/'I' used instead of Ukrainian 'і'/'І' inside Cyrillic words (cc_l25_simd, old requirements deck);
  * cp1251 mojibake ("Ìîòèâàöiÿ" → "Мотивація") in PDFs with broken ToUnicode maps;
  * partial (word-level) mojibake, '№' for «є', fl/fi/ff ligature glyphs stored as control chars (T2A fonts);
  * zero-width spaces, soft hyphens, apostrophe variants, ligatures.
"""

from __future__ import annotations

import re
import unicodedata

_CYR = "А-Яа-яЄєІіЇїҐґ'’ʼ"
_LATIN_I_IN_WORD = re.compile(
    rf"(?<=[{_CYR}])[iI]|[iI](?=[{_CYR}])"  # inside a Cyrillic word
    rf"|(?:(?<=[{_CYR}] )|(?<=[{_CYR}], ))[iI](?= [{_CYR}])"  # conjunction «і» between Cyrillic words
)
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f]")
_CTRL_DASH = re.compile(r"(?<=\s)[\x00-\x08\x0b-\x1f](?=\s|$)")  # a lone control glyph between spaces = dash
_MOJIBAKE = re.compile(r"[À-ÿ]{3,}")


_WORD = re.compile(r"[A-Za-zÀ-ÿ¨]+")
_LIG = {"\x1b": "ff", "\x1c": "fi", "\x1d": "fl", "\x1e": "ffi", "\x1f": "ffl"}  # T2A/LH font ligature slots
_LIG_RE = re.compile(r"(?<=[A-Za-z])[\x1b-\x1f]|[\x1b-\x1f](?=[A-Za-z])")
_HYPHEN_GLYPH = re.compile(r"(?<=[а-яіїєґ])[\x00\x1f](?=[а-яіїєґ])")  # discretionary hyphen glyph inside a word
_NUM_SIGN_IN_WORD = re.compile(r"(?<=[А-Яа-яЄєІіЇїҐґiI'])№(?!\d)")  # cp1251 artifact: «назива№ться» = «називається»
_NUM_SIGN_VERB = re.compile(
    r"(?<=[а-яіїєґ] )№(?=[ ,][а-яіїєґ ]|,)|(?<=\bi )№(?= [а-яіїєґ])|(?<!\w)№(?=[а-яіїєґ])"
)  # «струму № ампер» = «струму є ампер»


def _decode_cp1251(t: str) -> str:
    out = []
    for c in t.replace("¨", "ї"):  # these Type3 fonts put «ї» at 0xA8 («магi¨» = «магії»)
        if 0x80 <= ord(c) < 0x100:
            try:
                c = bytes([ord(c)]).decode("cp1251")
            except UnicodeDecodeError:
                pass
        out.append(c)
    return "".join(out)


def _word_stats(w: str) -> tuple[int, int]:
    """(#chars in À-ÿ or ¨, #ASCII letters other than i/I) — 'i' is a Ukrainian «і» in these fonts."""
    m = sum("À" <= c <= "ÿ" or c == "¨" for c in w)
    return m, sum(c.isascii() and c not in "iI" for c in w)


def fix_mojibake(t: str) -> str:
    """Repair cp1251 text decoded as latin-1.

    Whole line when ≥30% of its letters are in À-ÿ; otherwise word by word: a word is repaired when it has ≥2 À-ÿ
    characters and at most half as many other ASCII letters («Iëþñòðàöiÿ»; «café», «Ñandú» are safe). Short leftovers
    («ç», «iç», «Â» after a digit) are repaired when the line already has a repaired word or follows a digit.
    """
    letters = [c for c in t if c.isalpha()]
    if letters and _MOJIBAKE.search(t) and sum("À" <= c <= "ÿ" for c in letters) / len(letters) >= 0.3:
        return _decode_cp1251(t)
    words = list(_WORD.finditer(t))
    stats = [_word_stats(m.group(0)) for m in words]
    strong = {n for n, (m, a) in enumerate(stats) if m >= 2 and a * 2 <= m}
    todo = set(strong)
    for n, w in enumerate(words):
        m, a = stats[n]
        if n not in strong and m >= 1 and a == 0 and (strong or (w.start() > 0 and t[w.start() - 1].isdigit())):
            todo.add(n)
    if not todo:
        return t
    for n in sorted(todo, reverse=True):
        w = words[n]
        t = t[: w.start()] + _decode_cp1251(w.group(0)) + t[w.end() :]
    return t


def fix_cp1251_artifacts(t: str) -> str:
    """'№' standing where Cyrillic «є» should be (broken ToUnicode maps)."""
    t = _NUM_SIGN_IN_WORD.sub("є", t)
    return _NUM_SIGN_VERB.sub("є", t)


def fix_glyphs(t: str) -> str:
    """Ligature / hyphen glyphs that PDF fonts store in control-char slots. Call BEFORE whitespace collapsing
    (\\x1c-\\x1f count as whitespace for `\\s`)."""
    t = _LIG_RE.sub(lambda m: _LIG[m.group(0)], t)  # «\x1dip-\x1dop» = «flip-flop»
    return _HYPHEN_GLYPH.sub("", t)


def fix_latin_i(t: str) -> str:
    def rep(m: re.Match[str]) -> str:
        return "і" if m.group(0) == "i" else "І"

    prev = None
    while prev != t:  # words like "iнiцiалiзацiя" need several passes
        prev = t
        t = _LATIN_I_IN_WORD.sub(rep, t)
    return t


def clean(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    t = t.replace("​", "").replace("­", "").replace("﻿", "")
    t = t.replace("ʼ", "'").replace("’", "'")  # one apostrophe form → «пам'ять» matches in BM25
    t = t.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    t = fix_mojibake(t)
    t = fix_cp1251_artifacts(t)
    t = fix_glyphs(t)
    t = _CTRL_DASH.sub("–", t)  # T2A dash glyph (0x15) comes out as a control char
    t = _CTRL.sub('"', t)  # T2A quote glyphs come out as control chars too
    t = fix_latin_i(t)
    return t


def is_toc_line(t: str) -> bool:
    """Table-of-contents line with dot leaders: '1.2 Ціль роботи . . . . . . 3'."""
    return bool(re.search(r"(\.\s*){5,}\d+\s*$", t))
