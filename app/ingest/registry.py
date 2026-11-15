"""[DP] Build the document registry: which files are indexed, under which id, course(s) and type.

Rules (from data understanding, reports/review/*.md):
  * byte-identical files in several course folders → one document, several courses;
  * same filename stem with different content → one document (best version wins: clean text, newest),
    all courses kept, other copies recorded in `source_files`;
  * doc type / title / exclusion from `data/doc_overrides.yaml` first, filename heuristics second.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymupdf
import yaml

from app.config import ROOT, cfg, path
from app.ingest.convert import CONVERTIBLE, converted_path
from app.ingest.textnorm import fix_mojibake
from app.schemas import Document

OVERRIDES = ROOT / "data" / "doc_overrides.yaml"


def slugify(stem: str) -> str:
    s = re.sub(r"[^\w]+", "_", stem, flags=re.U).strip("_")
    return re.sub(r"_+", "_", s)


def guess_type(stem: str) -> str:
    s = stem.lower()
    if "силабус" in s or "requirements" in s or s.startswith("двв"):
        return "logistics"
    if "lab" in s or re.search(r"_p\d\d_", s):
        return "lab"
    return "lecture"


def guess_order(stem: str) -> float:
    for pat in (r"_l(\d+)", r"Le[ck]_(\d+)", r"_p(\d+)_"):
        m = re.search(pat, stem, re.I)
        if m:
            return float(m.group(1))
    return 999.0


def _mojibake_share(pdf: Path, pages: int = 5) -> float:
    doc = pymupdf.open(pdf)
    txt = "".join(doc[i].get_text() for i in range(min(pages, len(doc))))
    return 0.0 if not txt else sum(a != b for a, b in zip(txt, fix_mojibake(txt), strict=False)) / len(txt)


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def build() -> list[Document]:
    ov = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    files: dict[str, list[tuple[str, Path, Path]]] = {}  # stem → [(course, src, pdf)]
    for course, rel in cfg()["paths"]["raw_dirs"].items():
        for src in sorted((ROOT / rel).iterdir()):
            ext = src.suffix.lower()
            if ext == ".pdf":
                pdf = src
            elif ext in CONVERTIBLE:
                pdf = converted_path(src, course)
                if not pdf.exists():
                    raise FileNotFoundError(f"{pdf} missing — run `make convert`")
            else:
                continue
            files.setdefault(src.stem, []).append((course, src, pdf))

    docs = []
    for stem, copies in files.items():
        o = ov.get(stem, {})
        if o.get("exclude"):
            continue

        # best copy: least mojibake, then most recent PDF modification date
        def rank(c: tuple[str, Path, Path]) -> tuple[float, str]:
            md = pymupdf.open(c[2]).metadata or {}
            return (-_mojibake_share(c[2]), md.get("modDate") or "")

        best = max(copies, key=rank)
        pdf_doc = pymupdf.open(best[2])
        meta_title = (pdf_doc.metadata or {}).get("title") or ""
        courses = sorted({c for c, _, _ in copies}, key=lambda c: cfg()["courses"][c]["order"])
        docs.append(
            Document(
                doc_id=o.get("doc_id") or slugify(stem),
                courses=o.get("courses") or courses,
                doc_type=o.get("doc_type") or guess_type(stem),
                title=o.get("title") or meta_title.strip() or stem,
                source_files=[str(s.relative_to(ROOT)) for _, s, _ in copies],
                pdf_path=str(best[2].relative_to(ROOT)),
                n_pages=len(pdf_doc),
                order=o.get("order", guess_order(stem)),
            )
        )
    ids = [d.doc_id for d in docs]
    assert len(ids) == len(set(ids)), f"duplicate doc ids: {ids}"
    docs.sort(key=lambda d: (cfg()["courses"][d.courses[0]]["order"], d.order, d.doc_id))
    return docs


def save(docs: list[Document]) -> Path:
    out = path("parsed") / "documents.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([d.model_dump() for d in docs], ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load() -> list[Document]:
    raw = json.loads((path("parsed") / "documents.json").read_text(encoding="utf-8"))
    return [Document(**d) for d in raw]


if __name__ == "__main__":
    ds = build()
    save(ds)
    for d in ds:
        print(f"{'/'.join(d.courses):8s} {d.doc_type:9s} {d.order:5.0f} {d.n_pages:4d} {d.doc_id:40s} {d.title[:60]}")
