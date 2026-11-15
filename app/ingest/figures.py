"""[DP] C2a — decide which slides need a vision description, and render pages to PNG.

Signals (relative to a per-document baseline, because Beamer themes add ~20 vector drawings and
logo images to every page):
  * a non-repeating raster image covering ≥ `min_image_area` of the page;
  * vector drawing count above the document median by ≥ `min_drawings` (diagrams, circuits, timelines);
  * low extracted text but visible non-text content.
"""

from __future__ import annotations

import statistics
from collections import Counter
from functools import cache
from pathlib import Path

import pymupdf

from app.config import ROOT, cfg, path
from app.schemas import Slide


def page_png(pdf_path: str, page_no: int, dpi: int | None = None) -> bytes:
    """Render one page (1-based) to PNG bytes. Cached on disk under data/parsed/_pages/."""
    dpi = dpi or cfg()["ingest"]["render_dpi"]
    out = path("parsed") / "_pages" / Path(pdf_path).stem / f"p{page_no:03d}_{dpi}.png"
    if out.exists():
        return out.read_bytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    pix = _open(pdf_path)[page_no - 1].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    out.write_bytes(data)
    return data


@cache
def _open(pdf_path: str) -> pymupdf.Document:
    return pymupdf.open(ROOT / pdf_path)


def page_features(doc: pymupdf.Document) -> list[dict]:
    xref_pages: Counter[int] = Counter()
    for p in doc:
        xref_pages.update({img[0] for img in p.get_images(full=True)})
    n = len(doc)
    feats = []
    for p in doc:
        area = p.rect.width * p.rect.height
        big = 0.0
        for img in p.get_images(full=True):
            if n >= 4 and xref_pages[img[0]] / n > 0.3:  # theme/logo image repeated across pages
                continue
            for r in p.get_image_rects(img[0]):
                big = max(big, (r & p.rect).get_area() / area)
        feats.append({"img_area": big, "drawings": len(p.get_drawings()), "chars": len(p.get_text().strip())})
    return feats


def flag_slides(pdf_path: Path, slides: list[Slide]) -> list[Slide]:
    v = cfg()["ingest"]["vision"]
    doc = pymupdf.open(pdf_path)
    feats = page_features(doc)
    base_draw = statistics.median(f["drawings"] for f in feats) if feats else 0
    out = []
    for s in slides:
        f = feats[s.page_end - 1]  # the fullest overlay page
        extra_draw = f["drawings"] - base_draw
        reason = None
        if f["img_area"] >= v["min_image_area"]:
            reason = f"image {f['img_area']:.0%}"
        elif extra_draw >= v["min_drawings"]:
            reason = f"vector +{extra_draw:.0f}"
        elif len(s.body_md) < v["low_text_chars"] and (f["img_area"] > 0.02 or extra_draw >= 8):
            reason = "low text + graphics"
        out.append(s.model_copy(update={"needs_vision": reason is not None, "vision_reason": reason}))
    return out
