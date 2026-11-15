"""Citation verifier: does each answer sentence follow from the passages it cites?"""

from __future__ import annotations

import re

from app.llm import QuotaError, complete_json, load_prompt, trace_event
from app.pipeline.generate import chunks_for, format_passages
from app.pipeline.guard import esc
from app.schemas import Answer, Chunk, Hit, VerifyResult

_TAG = re.compile(r"\[S(\d+)\]")
_SENT = re.compile(r"[^\n]+?(?:[.!?…]+(?:\s*\[S\d+\])*(?=\s|$)|$)")
_LETTER = re.compile(r"[^\W\d_]")


def split_sentences(text: str) -> list[str]:
    """Split into sentences (trailing citation tags stay with their sentence); one line = at least one sentence."""
    out = [m.group(0).strip() for line in text.split("\n") for m in _SENT.finditer(line)]
    return [s for s in out if _LETTER.search(_TAG.sub("", s))]


def run(answer: Answer, hits: list[Hit], chunks: list[Chunk] | None = None) -> VerifyResult:
    if answer.abstained:
        return VerifyResult(supported=True)
    chunks = chunks if chunks is not None else chunks_for(hits)
    sentences = split_sentences(answer.text)
    if not sentences:
        return VerifyResult(supported=True)
    lines, used = [], set()
    for i, s in enumerate(sentences, 1):
        tags = [int(n) for n in _TAG.findall(s) if 1 <= int(n) <= len(chunks)]
        used.update(tags)
        lines.append(f"{i}. {s} (cites: {', '.join(f'S{n}' for n in tags) or 'none'})")
    cited = [(n, chunks[n - 1]) for n in sorted(used)]
    passages = "\n\n".join(format_passages([c]).replace("[S1]", f"[S{n}]", 1) for n, c in cited) or "(none)"
    try:
        data, _ = complete_json(
            load_prompt("verify"),
            "fast",
            step="verify",
            sentences=esc("\n".join(lines)),
            passages=passages,
        )
        idx = [int(i) for i in data.get("unsupported", []) if 1 <= int(i) <= len(sentences)]
        bad = [str(t) for t in data.get("bad_citations", [])]
    except QuotaError:
        raise  # quota must reach the UI banner / eval resume logic, never be hidden
    except Exception as e:  # noqa: BLE001 — verifier failure must not block the answer (fail open)
        trace_event("verify_error", error=repr(e)[:300])
        return VerifyResult(supported=True)
    unsupported = [sentences[i - 1] for i in dict.fromkeys(idx)]
    return VerifyResult(supported=not unsupported and not bad, unsupported_sentences=unsupported, bad_citations=bad)
