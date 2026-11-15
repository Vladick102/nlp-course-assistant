"""[DP] C1 — PDF → structured slides (PyMuPDF).

Format-agnostic: works on Beamer, PowerPoint-exported and plain LaTeX documents by using layout
statistics instead of per-template rules:
  * lines are rebuilt by baseline (PowerPoint splits justified lines into per-word spans);
  * boilerplate = text repeated on many pages, page numbers, small-font lines in header/footer bands;
  * title = largest-font text in the top part of the page (if clearly larger than body);
  * footnotes = small font below the body (not in the footer band);
  * monospace runs → fenced code; external link annotations → Markdown links;
  * Beamer overlays (page text ⊂ next page text, same title) are merged into one slide.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.config import cfg
from app.ingest.textnorm import clean, fix_glyphs, is_toc_line
from app.schemas import Slide

MONO_HINTS = ("mono", "courier", "consol", "cmtt", "lmtt", "inconsolata", "dejavusansm", "sourcecodepro")
BULLET_CHARS = "•◇◦▪▸►–‣∙●○■□➢✓"


@dataclass
class Line:
    text: str
    x0: float
    y0: float
    y1: float
    size: float
    mono: bool
    bold: bool
    spans: list[dict] = field(default_factory=list)
    bullet: bool = False  # starts a list item (glyph char or Beamer bullet image to the left)
    tx0: float = 0.0  # x where the text proper starts (after the bullet glyph)
    glyph_level: int = 0  # nesting hint from the bullet glyph run ("◇" → 1, "◇◇" → 2, ball image → 0)


def _is_mono(span: dict) -> bool:
    return bool(span["flags"] & 8) or any(h in span["font"].lower() for h in MONO_HINTS)


def page_lines(page: pymupdf.Page) -> list[Line]:
    """Group spans by baseline into visual lines (relative coords 0..1)."""
    W, H = page.rect.width, page.rect.height
    spans = []
    bullets: list[tuple[float, float]] = []  # (x1, y_mid) of tiny images = Beamer bullet balls
    # (explicit text flags drop image blocks, so tiny bullet images come from get_image_info)
    for info in page.get_image_info():
        x0, y0, x1, y1 = info["bbox"]
        if (x1 - x0) < 0.03 * W and (y1 - y0) < 0.03 * H:
            bullets.append((x1, (y0 + y1) / 2))
    for b in page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]:
        if b["type"] != 0:
            continue
        for ln in b["lines"]:
            if abs(ln["dir"][1]) > 0.2:  # rotated text (axis labels) — skip
                continue
            for s in ln["spans"]:
                if s["text"].strip():
                    spans.append(s)
    spans.sort(key=lambda s: (round(s["origin"][1], 0), s["origin"][0]))
    lines: list[list[dict]] = []
    for s in spans:
        if lines:
            last = lines[-1][-1]
            same_base = abs(s["origin"][1] - last["origin"][1]) <= max(1.5, 0.25 * s["size"])
            if same_base:
                lines[-1].append(s)
                continue
        lines.append([s])
    out = []
    for grp in lines:
        grp.sort(key=lambda s: s["bbox"][0])
        # drop footnote markers: superscript digits glued to words ("живучіший¹")
        big = max(s["size"] for s in grp)
        grp = [s for s in grp if not (s["size"] < 0.8 * big and re.fullmatch(r"\s*\d{1,3}\s*", s["text"]))] or grp
        parts: list[str] = []
        prev_x1 = None
        for s in grp:
            t = s["text"]
            if prev_x1 is not None and s["bbox"][0] - prev_x1 > 0.15 * s["size"] and not parts[-1].endswith(" "):
                t = " " + t.lstrip()
            parts.append(t)
            prev_x1 = s["bbox"][2]
        text = clean(re.sub(r"\s+", " ", fix_glyphs("".join(parts))).strip())
        text = re.sub(r" ([,.;:!?])(?=\s|$)", r"\1", text)  # gap left by a dropped footnote marker
        if not text or is_toc_line(text):
            continue
        main = max(grp, key=lambda s: len(s["text"].strip()))
        lx0 = min(s["bbox"][0] for s in grp)
        ly0, ly1 = min(s["bbox"][1] for s in grp), max(s["bbox"][3] for s in grp)
        img_bullet = any(bx1 <= lx0 + 1 and ly0 - 1 <= by <= ly1 + 1 for bx1, by in bullets)
        glyph_bullet = text[0] in BULLET_CHARS
        run = len(text) - len(text.lstrip(text[0])) if glyph_bullet else 0
        glyph_level = 0 if img_bullet or text[0] == "•" or not glyph_bullet else 1 + (run - 1 if text[0] in "◇◦" else 0)
        first_text = next((s for s in grp if s["text"].strip(BULLET_CHARS + " ")), grp[0])
        mono_chars = sum(len(s["text"]) for s in grp if _is_mono(s))
        out.append(
            Line(
                text=text,
                x0=min(s["bbox"][0] for s in grp) / W,
                y0=min(s["bbox"][1] for s in grp) / H,
                y1=max(s["bbox"][3] for s in grp) / H,
                size=main["size"],
                mono=mono_chars >= 0.6 * sum(len(s["text"]) for s in grp),
                bold=bool(main["flags"] & 16) or "bold" in main["font"].lower(),
                spans=grp,
                bullet=img_bullet or glyph_bullet,
                tx0=first_text["bbox"][0] / W,
                glyph_level=glyph_level,
            )
        )
    out.sort(key=lambda ln: (round(ln.y0, 3), ln.x0))
    return out


def _active_nav(ln: Line) -> str:
    """Beamer miniframe nav: the active section/subsection is drawn in a different (dark) colour."""
    colors = Counter(sp["color"] for sp in ln.spans)
    if len(colors) < 2:
        return ln.text
    darkest = min(colors, key=lambda c: sum((c >> k) & 255 for k in (0, 8, 16)))
    active = " ".join(sp["text"].strip() for sp in ln.spans if sp["color"] == darkest and sp["text"].strip())
    return clean(active)


def norm(t: str) -> str:
    t = re.sub(r"\d+", "#", t.lower())
    return re.sub(r"\W+", " ", t).strip()


def boilerplate_set(pages_lines: list[list[Line]], ratio: float) -> set[str]:
    """Normalized line texts that repeat on more than `ratio` of pages (headers, footers, author)."""
    n = len(pages_lines)
    if n < 4:
        return set()
    cnt: Counter[str] = Counter()
    for lines in pages_lines:
        cnt.update({norm(ln.text) for ln in lines if ln.y0 < 0.15 or ln.y1 > 0.85})
    return {t for t, c in cnt.items() if c / n > ratio and t}


def _links(page: pymupdf.Page) -> list[tuple[str, str]]:
    """External links as (anchor_text, uri), one per URI. Internal (goto) links are Beamer navigation → ignored.

    A URI wrapped over several lines has several annotation rects; their texts are joined in reading order.
    """
    pieces: dict[str, list[str]] = {}
    for lk in sorted(page.get_links(), key=lambda lk: (lk["from"].y0, lk["from"].x0)):
        uri = lk.get("uri")
        if not uri or not re.match(r"(https?|ftp|mailto):", uri):
            continue
        r = lk["from"]
        r = pymupdf.Rect(r.x0 + 0.5, r.y0 + 0.5, r.x1 - 0.5, r.y1 - 0.5)  # don't swallow neighbouring glyphs
        anchor = clean(re.sub(r"\s+", " ", page.get_textbox(r).strip()))
        parts = pieces.setdefault(uri, [])
        if anchor and anchor not in parts:
            parts.append(anchor)
    out = []
    for uri, parts in pieces.items():
        anchor = " ".join(parts)
        if anchor.replace(" ", "").startswith(("http", "ftp", "mailto")):
            anchor = uri  # bare URL printed on the slide (maybe wrapped): show the URI itself
        out.append((anchor, uri))
    return out


def _attach_links(body: str, links: list[tuple[str, str]]) -> str:
    extra = []
    for anchor, uri in links:
        if f"]({uri})" in body:
            continue
        m = None
        if len(anchor) >= 3:  # whitespace-insensitive search (the anchor may be wrapped in the body)
            m = re.search(r"\s+".join(re.escape(w) for w in anchor.split()), body)
        if m and body.count("```", 0, m.start()) % 2 == 0:  # never inject Markdown into a code fence
            body = body[: m.start()] + f"[{m.group(0)}]({uri})" + body[m.end() :]
        else:
            extra.append(f"- [{anchor or uri}]({uri})")
    if extra:
        body = (body + "\n\nПосилання:\n" + "\n".join(extra)).strip()
    return body


def _levels(xs: list[float]) -> list[float]:
    lv: list[float] = []
    for x in sorted(xs):
        if not lv or x - lv[-1] > 0.02:
            lv.append(x)
    return lv[:4]


def _render_body(lines: list[Line]) -> str:
    """Lines → Markdown. Code runs are fenced; wrapped lines are joined; bullets nested by text indent."""
    if not lines:
        return ""
    levels = _levels([ln.tx0 for ln in lines if ln.bullet and not ln.mono])
    out: list[str] = []
    in_code = False
    prev: Line | None = None
    for ln in lines:
        if ln.mono:
            if not in_code:
                out.append("```")
                in_code = True
            base = min((x.x0 for x in lines if x.mono), default=ln.x0)
            out.append(" " * max(0, int((ln.x0 - base) * 80)) + ln.text.replace("∗", "*"))
            prev = ln
            continue
        if in_code:
            out.append("```")
            in_code = False
        text = ln.text.lstrip(BULLET_CHARS + " ")
        if ln.text.startswith("### "):
            out.append(ln.text)
            prev = None
            continue
        gap = prev is not None and (ln.y0 - prev.y1) > 0.8 * (ln.y1 - ln.y0)
        numbered = re.match(r"\d{1,2}[.)]\s", ln.text) is not None  # "4. Поняття…" starts a new item
        cont = (
            prev is not None
            and not ln.bullet
            and not numbered
            and not gap
            and abs(ln.tx0 - prev.tx0) < 0.02
            and bool(out)
        )
        if cont:
            joiner = "" if out[-1].endswith("-") and not out[-1].endswith(" -") else " "
            out[-1] = (out[-1][:-1] if joiner == "" else out[-1]) + joiner + text
        elif ln.bullet:
            lvl = next((i for i, x in enumerate(levels) if ln.tx0 <= x + 0.01), len(levels) - 1)
            lvl = max(lvl, ln.glyph_level)
            out.append("  " * max(lvl, 0) + "- " + text)
        else:
            out.append(("\n" if gap and out else "") + text)
        prev = ln
    if in_code:
        out.append("```")
    return "\n".join(out).strip()


def parse_pdf(pdf_path: Path, doc_id: str) -> list[Slide]:
    ic = cfg()["ingest"]
    doc = pymupdf.open(pdf_path)
    all_lines = [page_lines(p) for p in doc]
    boiler = boilerplate_set(all_lines, ic["repeat_ratio"])
    sizes = [ln.size for lines in all_lines for ln in lines for _ in range(max(1, len(ln.text) // 20))]
    body_size = statistics.median(sizes) if sizes else 10.0

    # font size of the repeated footer line; non-repeating small text *larger* than that is a footnote
    foot_sizes = [
        ln.size for lines in all_lines for ln in lines if ln.y0 >= 1 - ic["footer_band"] and norm(ln.text) in boiler
    ]
    footer_size = statistics.median(foot_sizes) if foot_sizes else None

    slides: list[Slide] = []
    last_heading: str | None = None
    for i, (page, lines) in enumerate(zip(doc, all_lines, strict=True)):
        header_rows: list[str] = []
        keep: list[Line] = []
        foot: list[Line] = []
        for ln in lines:
            n = norm(ln.text)
            small = ln.size < 0.75 * body_size
            if re.fullmatch(r"[#\s/]*", n):  # page numbers like "5", "5 / 40"
                continue
            if ln.y1 <= ic["header_band"] and small:
                header_rows.append(_active_nav(ln))  # Beamer section bar
                continue
            if n in boiler:
                continue
            if ln.y0 >= 1 - ic["footer_band"] and small:
                if footer_size is None or ln.size <= 1.1 * footer_size:
                    continue  # footer / nav icons
                foot.append(ln)  # footnote that happens to sit inside the footer band
                continue
            if small and ln.y0 > 0.6:
                foot.append(ln)
                continue
            keep.append(ln)

        section = " › ".join(r for r in header_rows if r) or None
        # title: largest font in top 25% if clearly larger than body text (a big monospace title counts too)
        title = None
        top = [ln for ln in keep if ln.y0 < 0.25 and (not ln.mono or ln.size >= 1.3 * body_size)]
        if top:
            mx = max(ln.size for ln in top)
            if mx >= 1.05 * body_size:
                tl = [ln for ln in top if abs(ln.size - mx) < 0.5]
                title = " ".join(ln.text for ln in tl)
                keep = [ln for ln in keep if ln not in tl]
        # headings in document-style pages (lab handouts)
        heads = [ln for ln in keep if ln.size >= 1.15 * body_size and not ln.mono]
        if len(heads) > 0.5 * len(keep):  # mostly big text = a large-font body (PowerPoint), not headings
            heads = []
        if heads and not title:
            title = heads[0].text
        if heads:
            last_heading = heads[-1].text
        if not title and last_heading and len(doc) > 1:
            title = f"{last_heading} (продовження)"

        body_lines = []
        for ln in keep:
            if ln in heads and ln.text != title:
                body_lines.append(Line("### " + ln.text, ln.x0, ln.y0, ln.y1, ln.size, False, True))
            elif ln.text != title:
                body_lines.append(ln)
        body = _render_body(body_lines)
        links = _links(page)
        body = _attach_links(body, links)
        footnotes = [re.sub(r"^\d+\s*", "", ln.text) for ln in foot]
        slides.append(
            Slide(
                doc_id=doc_id,
                page_start=i + 1,
                page_end=i + 1,
                section=section,
                title=title,
                body_md=body,
                footnotes=footnotes,
                urls=[u for _, u in links],
            )
        )
    return merge_overlays(slides)


def _plain(s: Slide) -> str:
    return norm(" ".join([s.body_md, *s.footnotes]))


def merge_overlays(slides: list[Slide]) -> list[Slide]:
    """Beamer \\pause: page i content is a prefix/subset of page i+1 with the same title → keep the fuller one."""
    out: list[Slide] = []
    for s in slides:
        if out:
            p = out[-1]
            a, b = _plain(p), _plain(s)
            if p.title == s.title and a and (b.startswith(a) or _subset(a, b)):
                s = s.model_copy(update={"page_start": p.page_start})
                out[-1] = s
                continue
        out.append(s)
    return out


def _subset(a: str, b: str) -> bool:
    ta, tb = a.split(), b.split()
    if len(ta) < 3 or len(tb) <= len(ta):
        return False
    cb = Counter(tb)
    ca = Counter(ta)
    return all(cb[w] >= c for w, c in ca.items())


def slide_to_md(s: Slide) -> str:
    pages = f"{s.page_start}" if s.page_start == s.page_end else f"{s.page_start}–{s.page_end}"
    parts = [f"## Слайд {pages} — {s.title or '(без заголовка)'}"]
    if s.section:
        parts.append(f"*Розділ: {s.section}*")
    if s.body_md:
        parts.append(s.body_md)
    for f in s.footnotes:
        parts.append(f"> Примітка: {f}")
    if s.figure_description:
        parts.append(f"[Опис зображення, згенеровано моделлю]\n{s.figure_description}")
    return "\n\n".join(parts)
