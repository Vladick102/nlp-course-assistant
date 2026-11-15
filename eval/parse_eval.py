"""[EVAL] C1 parser evaluation: our parser vs the pymupdf4llm baseline.

Gold items (eval/data/parse_gold.jsonl, or --gold PATH), one JSON per line:
  {doc_id, page, gold_title, gold_text, gold_urls}
Metrics (n, mean over items):
  * token-F1 and CER of the slide text vs gold_text (ours = body_md + footnotes, title excluded;
    markdown markup, link syntax and whitespace are normalised away on both sides),
  * title accuracy, exact and fuzzy (difflib ratio >= 0.85), ours only,
  * link recall / precision vs gold_urls (micro-averaged),
  * boilerplate leakage: share of items whose output still contains a repeated header/footer string
    (parser.boilerplate_set on the document) or the author line,
plus a gold-free automatic check over ALL documents: every external URI annotation in the PDF vs the urls
kept in data/parsed/<doc>/slides.jsonl (link recall).

Usage: uv run python -m eval.parse_eval [--gold PATH] [--no-auto] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

import pymupdf

from app.config import ROOT
from app.ingest import registry
from app.ingest.parser import boilerplate_set, norm, page_lines, parse_pdf
from app.ingest.run import load_slides, strip_license
from app.schemas import Document, Slide
from eval.metrics import cer, token_f1

DEFAULT_GOLD = ROOT / "eval" / "data" / "parse_gold.jsonl"
AUTHOR_RE = re.compile(r"Олег\s+Фаренюк", re.I)
URI_RE = re.compile(r"(?:https?|ftp|mailto):[^\s)\]>\"']+")
MIN_BOILER_LEN = 12  # shorter repeated strings (section names, "Огляд") would match ordinary prose
FUZZY_TITLE = 0.85


# ------------------------------------------------------------------ normalisation
def normalize_text(t: str) -> str:
    """Strip markdown markup so Markdown flavours compare equal to plain gold text."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)  # images
    t = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1", t)  # [anchor](uri) → anchor
    t = re.sub(r"^\s*>\s?(Примітка:)?", "", t, flags=re.M)
    t = re.sub(r"^\s*(?:#{1,6}\s+|[-*+•◇]\s+)", "", t, flags=re.M)
    t = re.sub(r"```\w*", " ", t)
    t = re.sub(r"[*_`|]+", "", t)
    t = t.replace("Посилання:", " ")
    return re.sub(r"\s+", " ", t).strip()


def urls_in(md: str) -> set[str]:
    return {u.rstrip(".,;") for u in URI_RE.findall(md)}


# ------------------------------------------------------------------ per-document cached artefacts
@cache
def doc_by_id(doc_id: str) -> Document:
    return next(d for d in registry.load() if d.doc_id == doc_id)


@cache
def our_slides(doc_id: str) -> tuple[Slide, ...]:
    d = doc_by_id(doc_id)
    return tuple(strip_license(s) for s in parse_pdf(ROOT / d.pdf_path, doc_id))


@cache
def boiler(doc_id: str) -> frozenset[str]:
    from app.config import cfg

    pdf = pymupdf.open(ROOT / doc_by_id(doc_id).pdf_path)
    b = boilerplate_set([page_lines(p) for p in pdf], cfg()["ingest"]["repeat_ratio"])
    return frozenset(x for x in b if len(x) >= MIN_BOILER_LEN)


def our_output(doc_id: str, page: int) -> tuple[str, str | None, set[str]]:
    """(text, title, urls) of the slide covering `page`."""
    s = next((s for s in our_slides(doc_id) if s.page_start <= page <= s.page_end), None)
    if s is None:  # dropped as empty / not parsed
        return "", None, set()
    return "\n".join([s.body_md, *s.footnotes]), s.title, set(s.urls)


def baseline_output(doc_id: str, page: int) -> str:
    import pymupdf4llm

    pdf = str(ROOT / doc_by_id(doc_id).pdf_path)
    return pymupdf4llm.to_markdown(pdf, pages=[page - 1], show_progress=False)


def leaks(doc_id: str, text: str) -> bool:
    n = norm(text)
    return bool(AUTHOR_RE.search(text)) or any(b in n for b in boiler(doc_id))


# ------------------------------------------------------------------ gold evaluation
def title_match(pred: str | None, gold: str | None) -> tuple[bool, bool]:
    if not gold:
        return (pred is None, pred is None)
    if not pred:
        return (False, False)
    a, b = pred.casefold().strip(), gold.casefold().strip()
    return (a == b, SequenceMatcher(None, a, b).ratio() >= FUZZY_TITLE)


def mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def prf(tp: int, n_pred: int, n_gold: int) -> dict:
    p = tp / n_pred if n_pred else None
    r = tp / n_gold if n_gold else None
    return {"precision": None if p is None else round(p, 4), "recall": None if r is None else round(r, 4)}


def eval_gold(items: list[dict]) -> dict:
    acc: dict[str, dict[str, list]] = {k: {"f1": [], "cer": [], "leak": []} for k in ("ours", "baseline")}
    link = {k: [0, 0, 0] for k in acc}  # tp, n_pred, n_gold
    t_exact, t_fuzzy, per_item = [], [], []
    for it in items:
        doc_id, page = it["doc_id"], int(it["page"])
        gold = normalize_text(it["gold_text"])
        gold_urls = set(it.get("gold_urls") or [])
        text, title, urls = our_output(doc_id, page)
        base = baseline_output(doc_id, page)
        outs = {"ours": (text, urls), "baseline": (base, urls_in(base))}
        row = {"doc_id": doc_id, "page": page}
        for name, (out, found) in outs.items():
            n = normalize_text(out)
            f1, c = token_f1(n, gold), cer(n, gold)
            acc[name]["f1"].append(f1)
            acc[name]["cer"].append(c)
            acc[name]["leak"].append(float(leaks(doc_id, out)))
            link[name][0] += len(found & gold_urls)
            link[name][1] += len(found)
            link[name][2] += len(gold_urls)
            row[name] = {"f1": round(f1, 3), "cer": round(c, 3), "urls": sorted(found)}
        ex, fz = title_match(title, it.get("gold_title"))
        t_exact.append(float(ex))
        t_fuzzy.append(float(fz))
        row["title"] = {"pred": title, "gold": it.get("gold_title"), "exact": ex}
        per_item.append(row)
    return {
        "n": len(items),
        "metrics": {
            name: {
                "token_f1": mean(a["f1"]),
                "cer": mean(a["cer"]),
                "boilerplate_leakage": mean(a["leak"]),
                **{f"link_{k}": v for k, v in prf(*link[name]).items()},
            }
            for name, a in acc.items()
        },
        "title_accuracy": {"exact": mean(t_exact), "fuzzy": mean(t_fuzzy)},
        "items": per_item,
    }


# ------------------------------------------------------------------ gold-free link recall (all docs)
def pdf_links(pdf: Path) -> set[tuple[int, str]]:
    return {
        (i + 1, lk["uri"])
        for i, p in enumerate(pymupdf.open(pdf))
        for lk in p.get_links()
        if re.match(r"(https?|ftp|mailto):", lk.get("uri") or "")
    }


def auto_link_recall() -> dict:
    per_doc, tot_found, tot = [], 0, 0
    for d in registry.load():
        try:
            slides = load_slides(d.doc_id)
        except FileNotFoundError:
            continue
        want = pdf_links(ROOT / d.pdf_path)
        if not want:
            continue
        have = {(s.page_start, s.page_end, u) for s in slides for u in s.urls}
        found = {(p, u) for p, u in want if any(a <= p <= b and u == v for a, b, v in have)}
        per_doc.append(
            {"doc_id": d.doc_id, "links": len(want), "found": len(found), "missing": sorted(want - found)[:5]}
        )
        tot_found += len(found)
        tot += len(want)
    return {
        "docs_with_links": len(per_doc),
        "links": tot,
        "found": tot_found,
        "recall": round(tot_found / tot, 4) if tot else None,
        "per_doc": per_doc,
    }


# ------------------------------------------------------------------ report
def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def markdown(res: dict) -> str:
    out = []
    if "gold" in res:
        g = res["gold"]
        out += [f"### Parser vs gold (n={g['n']})", "", "| metric | ours | pymupdf4llm |", "|---|---|---|"]
        mo, mb = g["metrics"]["ours"], g["metrics"]["baseline"]
        for k, label in [
            ("token_f1", "token-F1 ↑"),
            ("cer", "CER ↓"),
            ("link_recall", "link recall ↑"),
            ("link_precision", "link precision ↑"),
            ("boilerplate_leakage", "boilerplate leakage ↓"),
        ]:
            out.append(f"| {label} | {fmt(mo[k])} | {fmt(mb[k])} |")
        t = g["title_accuracy"]
        out += [f"| title accuracy exact / fuzzy | {fmt(t['exact'])} / {fmt(t['fuzzy'])} | n/a |", ""]
    a = res.get("auto_links")
    if a:
        out += [
            "### Gold-free link recall (all documents)",
            "",
            f"{a['found']}/{a['links']} external URI annotations kept in slides.jsonl "
            f"(recall {fmt(a['recall'])}, {a['docs_with_links']} documents with links).",
            "",
        ]
        bad = [d for d in a["per_doc"] if d["found"] < d["links"]]
        if bad:
            out += ["| doc | found/links | e.g. missing |", "|---|---|---|"]
            out += [f"| {d['doc_id']} | {d['found']}/{d['links']} | {d['missing'][:2]} |" for d in bad]
    return "\n".join(out)


def run(gold: Path | None = None, auto: bool = True) -> dict:
    res: dict = {"date": str(date.today())}
    gold = gold or DEFAULT_GOLD
    if gold.exists():
        items = [json.loads(ln) for ln in gold.read_text(encoding="utf-8").splitlines() if ln.strip()]
        res["gold_file"] = str(gold)
        res["gold"] = eval_gold(items)
    else:
        print(f"[parse_eval] gold file {gold} not found; running gold-free checks only")
    if auto:
        res["auto_links"] = auto_link_recall()
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path)
    ap.add_argument("--no-auto", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    res = run(a.gold, not a.no_auto)
    out = a.out or ROOT / "reports" / "eval" / f"parser_{date.today()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(markdown(res))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
