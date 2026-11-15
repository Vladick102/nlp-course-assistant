"""Parser tests on real course PDFs (a few pages each) plus synthetic overlay-merge cases."""

from functools import cache
from pathlib import Path

import pymupdf
import pytest

from app.config import ROOT
from app.ingest.parser import _attach_links, merge_overlays, page_lines, parse_pdf
from app.schemas import Slide

INTRO = ROOT / "os/os_l000_intro.pdf"
LINUX = ROOT / "os/os_l040_Linux_internals.pdf"
SIMD = ROOT / "aks/cc_l25_simd.pdf"
LEK3 = ROOT / "pok/Lek_3_2018.pdf"

pytestmark = pytest.mark.skipif(not INTRO.exists(), reason="raw course PDFs not available")


@cache
def parsed(pdf: Path) -> tuple[Slide, ...]:
    return tuple(parse_pdf(pdf, pdf.stem))


def slide(pdf: Path, page: int) -> Slide:
    return next(s for s in parsed(pdf) if s.page_start <= page <= s.page_end)


def test_title_and_section_beamer():
    s = slide(INTRO, 4)
    assert s.title == "Абстракції, які надаються ОС загального використання"
    assert s.section == "Огляд"


def test_header_footer_stripped():
    for s in parsed(INTRO)[1:]:  # p1 carries the license line, removed later by ingest.run.strip_license
        assert "Фаренюк" not in s.body_md + " ".join(s.footnotes), s.page_start
        assert "Що таке операційна система і навіщо вона" not in s.body_md


def test_footnote_in_footer_band_captured():
    s = slide(INTRO, 4)
    assert "Legacy, але все ще часто незамінні." in s.footnotes
    assert "Legacy" not in s.body_md


def test_bullet_images_and_nesting():
    body = slide(INTRO, 4).body_md.splitlines()
    assert body[0] == "- Ключовим є поняття віртуалізації."
    assert any(ln.startswith("  - Мережеві пристрої") for ln in body)  # ◇ item nested under the ball item
    assert any(ln.startswith("    - Віртуалізація GPU") for ln in body)  # ◇◇ is one level deeper


def test_external_links_extracted():
    pages = [
        (i + 1, lk["uri"])
        for i, p in enumerate(pymupdf.open(INTRO))
        for lk in p.get_links()
        if lk.get("uri", "").startswith("http")
    ]
    assert pages, "fixture assumption: os_l000_intro has external links"
    for pno, uri in set(pages):
        s = slide(INTRO, pno)
        assert uri in s.urls and f"]({uri})" in s.body_md
        assert s.urls.count(uri) == 1  # wrapped links are deduplicated


def test_anchor_text_link_inline():
    s = slide(INTRO, 12)
    assert "[”Windows NT vs. Unix: A design comparison”](https://blogsystem5.substack.com" in s.body_md


def test_mojibake_repaired_in_nav_bar():
    doc = pymupdf.open(LINUX)
    assert "Ïðîöåñè" in doc[1].get_text()  # raw text really is cp1251-as-latin1 garbage
    text = " ".join(ln.text for ln in page_lines(doc[1]))
    assert "Процеси і потоки" in text
    assert "Ï" not in text


def test_t2a_dash_glyph_not_a_quote():
    s = slide(LINUX, 2)
    assert "трохи – стандартною" in s.body_md and '"' not in s.body_md


def test_latin_i_fixed():
    s = slide(SIMD, 2)
    assert "курсі" in s.body_md and "більше" in s.body_md and "курсi" not in s.body_md


def test_powerpoint_title_and_large_body():
    assert slide(LEK3, 4).title == "Біт, байт, слово (1)"
    assert "###" not in slide(LEK3, 2).body_md  # big-font body text is not turned into headings
    assert "\n5. " in slide(LEK3, 2).body_md  # numbered items stay separate


def _s(page: int, title: str | None, body: str, **kw) -> Slide:
    return Slide(doc_id="d", page_start=page, page_end=page, title=title, body_md=body, **kw)


def test_overlay_merge_prefix_and_subset():
    slides = [
        _s(1, "A", "- one"),
        _s(2, "A", "- one\n- two"),
        _s(3, "A", "- one\n- two\n- three"),
        _s(4, "B", "- one\n- two\n- three\n- four"),  # different title: not merged
        _s(5, "C", "alpha beta gamma delta"),
    ]
    out = merge_overlays(slides)
    assert [(s.page_start, s.page_end) for s in out] == [(1, 3), (4, 4), (5, 5)]
    assert out[0].body_md.endswith("three")


def test_overlay_merge_keeps_distinct_slides():
    slides = [_s(1, "A", "- one two three"), _s(2, "A", "- completely different content here")]
    assert len(merge_overlays(slides)) == 2


def test_attach_links_wrapped_and_code_fence():
    body = "see the Unix\ntimeline page\n```\nhttp://x.org/a\n```"
    out = _attach_links(body, [("Unix timeline", "http://u.org"), ("http://x.org/a", "http://x.org/a")])
    assert "[Unix\ntimeline](http://u.org)" in out
    assert "```\nhttp://x.org/a\n```" in out  # fence untouched
    assert out.endswith("- [http://x.org/a](http://x.org/a)")


def _page_text(pdf: Path, page: int) -> str:
    return " ".join(ln.text for ln in page_lines(pymupdf.open(pdf)[page - 1]))


def test_partial_mojibake_on_real_pages():
    l4 = ROOT / "pok/pok_l04_simple_logic.pdf"
    l5 = ROOT / "pok/pok_l05_sequential_logic.pdf"
    t = _page_text(l4, 108)
    assert "Ілюстрація з Andrew" in t and "ç" not in t and not any("À" <= c <= "ÿ" for c in t)
    assert "3.3В" in _page_text(l5, 73)


def test_fl_ligature_glyph_on_real_page():
    t = _page_text(ROOT / "pok/pok_l05_sequential_logic.pdf", 2)
    assert "(flip-flop)" in t
