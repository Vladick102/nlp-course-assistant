"""[EVAL] One harness for all component evaluations (resumable, quota-aware).

  uv run python -m eval.run --component C --split dev|test [--limit N] [--gold PATH] [--preset small] [--dry-run]
C in router | gate | answer | logistics | verify | e2e | all.
(retrieval/parser: eval/retrieval_eval.py, eval/parse_eval.py; `all` calls them too.)

Every finished item is appended at once to reports/eval/runs/<run_id>/<component>.jsonl;
re-running the same command skips finished items (app/llm.py also caches
identical calls on disk). On QuotaError the run stops cleanly:
  «Quota reached: N/M done; resume with the same command after <reset time> or with another key»  (exit code 2).
Judging is offline (no API): eval.judge_tasks -> Haiku agents (skill judge-batch) -> eval.score.

--preset small (same-day budget): router 20 stratified, answer 12 QA (3 per type), unanswerable 5, logistics 5, verify 5
perturbed items; gate runs on ALL QA+unanswerable (no LLM). Ids are sampled with a fixed seed and saved in the run dir.
`--split dev` falls back to eval/data/review/<set>.jsonl (unreviewed drafts) when eval/data/<set>_dev.jsonl is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.config import ROOT, cfg
from app.llm import QuotaError, collect_calls, new_trace
from eval import runs, score
from eval.runs import RunStore, read_jsonl

DATA = ROOT / "eval" / "data"
SEED = 20261115
PRESET_SMALL = {"router": 20, "qa_per_type": 3, "unanswerable": 5, "logistics": 5, "verify": 5}
LLM_COMPONENTS = ["router", "answer", "logistics", "verify"]
ALL_ORDER = ["gate", "retrieval", "parser", "router", "answer", "logistics", "verify", "e2e"]
FABRICATED = [
    "Цю концепцію вперше формалізували у 1987 році на конференції в Цюріху, і відтоді вона є стандартом ISO.",
    "За даними лекції, така реалізація працює приблизно у 40 разів швидше за будь-яку альтернативу.",
    "Автором цього підходу є Дональд Кнут, який запровадив його в першому виданні своєї книги про алгоритми.",
]


class ItemError(RuntimeError):
    """A non-quota failure for one item: the item is not stored (re-run retries it)."""


class TransientError(ItemError):
    """Congestion-type failure (providers rate-limited / timed out, router fell back): wait and retry the same item."""


BACKOFF_S = (30, 60, 120, 240)  # then 240 s repeatedly
GIVE_UP_AFTER_S = 15 * 60
sleep = time.sleep  # monkeypatched in tests


def backoff_schedule(total: int = GIVE_UP_AFTER_S) -> list[int]:
    """Waits between attempts: 30, 60, 120, 240, 240, ... until the waits would exceed `total` seconds."""
    out: list[int] = []
    while sum(out) + (w := BACKOFF_S[min(len(out), len(BACKOFF_S) - 1)]) <= total:
        out.append(w)
    return out


class QuotaStop(RuntimeError):
    def __init__(self, component: str, n_done: int, n_total: int, reset: str, kind: str = "daily_free_limit"):
        self.component, self.n_done, self.n_total, self.reset, self.kind = component, n_done, n_total, reset, kind
        super().__init__(self.message())

    def message(self) -> str:
        head = f"Quota reached: {self.n_done}/{self.n_total} done ({self.component})"
        tail = "resume with the same command"
        if self.kind in ("auth", "no_credits"):
            return f"{head}: API key problem ({self.kind}); fix OPENROUTER_API_KEY (.env or UI) and {tail}"
        if self.kind == "rate_limited":
            return f"{head}: providers congested; {tail} in a few minutes or with another key"
        return f"{head}: daily limit; reset ~{self.reset} or switch key; {tail}"


def reset_text(e: QuotaError) -> str:
    if e.reset_at:
        return e.reset_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") + (" (approx.)" if e.approximate else "")
    return "00:00 UTC"


# ------------------------------------------------------------------ gold loading
def gold_path(set_name: str, split: str, override: Path | None = None) -> tuple[Path, str]:
    """(path, source): source is 'reviewed' or 'unreviewed draft' (dev falls back to eval/data/review/<set>.jsonl)."""
    if override:
        return override, "explicit --gold"
    p = DATA / f"{set_name}_{split}.jsonl"
    if p.exists():
        return p, "reviewed"
    draft = DATA / "review" / f"{set_name}.jsonl"
    if split == "dev" and draft.exists():
        return draft, "unreviewed draft"
    raise SystemExit(f"gold file not found: {p}" + (" (no draft fallback for test)" if split != "dev" else ""))


def load_gold(
    set_name: str, split: str, override: Path | None = None, limit: int | None = None
) -> tuple[list[dict], str]:
    p, source = gold_path(set_name, split, override)
    items = read_jsonl(p)
    return (items[:limit] if limit else items), source


# ------------------------------------------------------------------ preset sampling
def pick_spread(items: list[dict], n: int, rng: random.Random, key: str = "course") -> list[dict]:
    """n items round-robin across groups of `key` (groups and members shuffled with rng)."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(str(it.get(key)), []).append(it)
    for g in groups.values():
        rng.shuffle(g)
    order = list(groups)
    rng.shuffle(order)
    out: list[dict] = []
    while len(out) < n and any(groups.values()):
        for k in order:
            if groups[k] and len(out) < n:
                out.append(groups[k].pop())
    return out


def sample_router(items: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Stratified: n/5 per route, each route contributes one hard item first (>=4 hard in total when available)."""
    routes = score.ROUTES
    per = max(1, n // len(routes))
    out: list[dict] = []
    for route in routes:
        pool = [i for i in items if i["route"] == route]
        rng.shuffle(pool)
        hard = [i for i in pool if i.get("hard")]
        rest = [i for i in pool if not i.get("hard")]
        pick = hard[:1] + rest[: per - len(hard[:1])]
        pick += [i for i in hard[1:] + rest[per - len(hard[:1]) :] if i not in pick][: per - len(pick)]
        out += pick
    return out


def sample_qa(items: list[dict], per_type: int, rng: random.Random) -> list[dict]:
    out: list[dict] = []
    for t in ("single", "figure", "multi", "real"):
        out += pick_spread([i for i in items if i.get("type") == t], per_type, rng)
    return out


def preset_sample(gold: dict[str, list[dict]], store: RunStore) -> dict[str, list[str]]:
    """Fixed-seed ids per set; persisted in <run>/sample.json (together with the verify ids) and reused on resume."""
    p = store.dir / "sample.json"
    saved = read_json(p) or {}
    samplers: dict[str, Callable[[list[dict], random.Random], list[dict]]] = {
        "router": lambda it, r: sample_router(it, PRESET_SMALL["router"], r),
        "qa": lambda it, r: sample_qa(it, PRESET_SMALL["qa_per_type"], r),
        "unanswerable": lambda it, r: pick_spread(it, PRESET_SMALL["unanswerable"], r),
        "logistics": lambda it, r: pick_spread(it, PRESET_SMALL["logistics"], r),
    }
    out: dict[str, list[str]] = {}
    for name, items in gold.items():
        ids = saved.get(name)
        if not ids or not set(ids) <= {i["id"] for i in items}:
            ids = [i["id"] for i in samplers[name](items, random.Random(f"{SEED}-{name}"))]
        out[name] = ids
    write_json(p, {**saved, **out})
    return out


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ generic resumable loop
def run_items(
    store: RunStore,
    component: str,
    split: str,
    items: list[dict],
    fn: Callable[[dict], dict],
    set_name: str = "",
    log: Callable[[str], None] = print,
) -> dict:
    """Run fn(item) for every item not yet stored; append each record immediately. Raises QuotaStop on QuotaError."""
    done = store.done_ids(component, split)
    todo = [i for i in items if i["id"] not in done]
    n_total, errors = len(items), 0
    n_done = len(items) - len(todo)
    for item in todo:
        waits = backoff_schedule()
        attempt = 0
        while True:
            attempt += 1
            try:
                rec = fn(item)
                break
            except (QuotaError, TransientError) as e:
                kind = e.kind if isinstance(e, QuotaError) else "rate_limited"
                if isinstance(e, QuotaError) and kind != "rate_limited":
                    raise QuotaStop(component, n_done, n_total, reset_text(e), kind) from e
                model = getattr(e, "model", "?")
                if attempt > len(waits):
                    errors += 1
                    msg = f"gave up after {sum(waits)} s of congestion ({kind}, {model})"
                    log(f"  [{component}] {item['id']}: {msg}; recorded as error item, continuing")
                    store.append_error(component, {"id": item["id"], "split": split, "error": msg})
                    rec = None
                    break
                w = waits[attempt - 1]
                log(
                    f"  [{component}] {datetime.now():%H:%M:%S} {item['id']}: {kind} (model {model}), "
                    f"attempt {attempt}, waiting {w} s"
                )
                sleep(w)
            except ItemError as e:
                errors += 1
                log(f"  [{component}] {item['id']}: not stored ({e})")
                store.append_error(component, {"id": item["id"], "split": split, "error": str(e)})
                rec = None
                break
        if rec is None:
            continue
        rec = {**rec, "id": item["id"], "split": split, "set": set_name or component, "run_id": store.run_id}
        rec["ts"] = datetime.now(UTC).isoformat(timespec="seconds")
        store.append(component, rec)
        n_done += 1
        log(f"  [{component}] {n_done}/{n_total} {item['id']}")
    return {
        "component": component,
        "n_total": n_total,
        "n_done": n_done,
        "n_skipped": len(items) - len(todo),
        "errors": errors,
    }


# ------------------------------------------------------------------ per-item functions (pipeline calls live here)
def _turns(history: list[dict] | None):
    from app.schemas import Turn

    return [Turn(**t) for t in history or []]


def router_fn(item: dict) -> dict:
    from app.pipeline import router

    new_trace("ev-router")
    calls = collect_calls()
    t0 = time.perf_counter()
    rd = router.run(item["question"], _turns(item.get("history")))
    if rd.reason.startswith("router failed"):  # router.run swallowed an all-models failure (timeouts): not a real label
        raise TransientError(rd.reason)
    return {
        "question": item["question"],
        "gold_route": item["route"],
        "gold_course": item.get("course"),
        "hard": bool(item.get("hard")),
        "route": rd.route,
        "course": rd.course,
        "confidence": rd.confidence,
        "reason": rd.reason,
        "queries": rd.queries,
        "llm_calls": calls,
        "latency_s": round(time.perf_counter() - t0, 3),
    }


def quota_from_debug(dbg: dict) -> QuotaError | None:
    """answer.run swallows QuotaError into debug['error_kind']=='quota'; rebuild it so the harness can stop."""
    if dbg.get("error_kind") != "quota":
        return None
    q = dbg.get("quota") or {}
    reset = datetime.fromisoformat(q["reset_at_iso"]) if q.get("reset_at_iso") else None
    return QuotaError(q.get("kind", "daily_free_limit"), q.get("model", "?"), "", reset, bool(q.get("approximate")))


def answer_record(item: dict, ans, latency: float) -> dict:
    d = ans.debug
    keep = (
        "route",
        "queries",
        "course_filter",
        "course_filter_dropped",
        "gate",
        "hits",
        "timings",
        "chunks_in_prompt",
        "verify",
        "abstain_by",
    )
    return {
        "question": item["question"],
        "gold_chunk_ids": item.get("gold_chunk_ids", []),
        "gold_doc_ids": item.get("gold_doc_ids", []),
        "reference_answer": item.get("reference_answer"),
        "key_facts": item.get("key_facts", []),
        "type": item.get("type"),
        "course": item.get("course"),
        "lang": item.get("lang"),
        "route": ans.route,
        "text": ans.text,
        "citations": [c.model_dump(include={"tag", "chunk_id", "doc_id", "label"}) for c in ans.citations],
        "invalid_citations": ans.invalid_citations,
        "abstained": ans.abstained,
        "trace_id": ans.trace_id,
        "debug": {k: d[k] for k in keep if k in d},
        "llm_calls": d.get("llm_calls", []),
        "latency_s": round(latency, 3),
    }


def make_pipeline_fn(run_pipeline: Callable | None = None) -> Callable[[dict], dict]:
    """fn(item) -> record via app.pipeline.answer.run (or an injected stand-in for tests)."""

    def fn(item: dict) -> dict:
        run = run_pipeline
        if run is None:
            from app.pipeline import answer

            run = answer.run
        t0 = time.perf_counter()
        ans = run(item["question"], _turns(item.get("history")))
        q = quota_from_debug(ans.debug)
        if q is not None:
            raise q
        if (ans.debug.get("route") or {}).get("reason", "").startswith("router failed"):
            raise TransientError("router fell back (all models failed)")
        if ans.debug.get("error"):
            raise ItemError(ans.debug["error"][:120])
        return answer_record(item, ans, time.perf_counter() - t0)

    return fn


def gate_fn(item: dict) -> dict:
    """No LLM: retrieve + rerank with the gold course hint (stands in for a correct router) and keep the top score."""
    from app.pipeline import rerank, retrieve

    q = item["question"]
    t0 = time.perf_counter()
    hits = rerank.run(q, retrieve.run([q], item.get("course")))
    top = max((h.score for h in hits), default=0.0)
    gold = item.get("gold_chunk_ids") or []
    return {
        "question": q,
        "answerable": "gold_chunk_ids" in item and bool(gold),
        "top_score": float(top),
        "top_chunks": [h.chunk_id for h in hits],
        "gold_in_top": score.cites_gold([h.chunk_id for h in hits], gold) if gold else None,
        "llm_calls": [],
        "latency_s": round(time.perf_counter() - t0, 3),
    }


# ------------------------------------------------------------------ verify perturbation test
def fabricate(text: str) -> tuple[str, str]:
    """Append a fabricated sentence with a valid-looking citation [S1]. Returns (new_text, sentence_without_nothing)."""
    s = FABRICATED[int(hashlib.sha256(text.encode()).hexdigest(), 16) % len(FABRICATED)] + " [S1]"
    return f"{text.rstrip()}\n{s}", s


def swap_citation(text: str, chunk_ids: list[str]) -> tuple[str, str, str] | None:
    """Replace the tags of the first cited sentence by a tag of a different passage (preferably another document).
    Returns (new_text, new_sentence, new_tag) or None when impossible."""
    import re

    from app.pipeline.verify import split_sentences

    tag_re = re.compile(r"\[S(\d+)\]")
    k = len(chunk_ids)
    for sent in split_sentences(text):
        own = {int(n) for n in tag_re.findall(sent) if 1 <= int(n) <= k}
        if not own:
            continue
        docs = {chunk_ids[n - 1].split("#")[0] for n in own}
        others = [n for n in range(1, k + 1) if n not in own]
        pref = [n for n in others if chunk_ids[n - 1].split("#")[0] not in docs] or others
        if not pref:
            continue
        new_tag = pref[0]
        body = tag_re.sub("", sent).rstrip()
        new_sent = f"{body} [S{new_tag}]"
        return text.replace(sent, new_sent, 1), new_sent, f"S{new_tag}"
    return None


def verify_eligible(rec: dict) -> bool:
    return (
        score.is_judgeable(rec)
        and rec.get("route") == "content"
        and bool(rec.get("citations"))
        and bool((rec.get("debug") or {}).get("chunks_in_prompt"))
    )


def verify_fn_factory(
    kinds: Callable[[dict], tuple[str, ...]], control: bool, verify_run: Callable | None = None, chunk_lookup=None
):
    """fn(answer_record) -> perturbation result. `kinds(rec)` decides which perturbations run for a record."""

    def fn(rec: dict) -> dict:
        from app.schemas import Answer

        vr = verify_run
        if vr is None:
            from app.pipeline import verify

            vr = verify.run
        lookup = chunk_lookup
        if lookup is None:
            from app import store

            lookup = store.chunks()
        ids = rec["debug"]["chunks_in_prompt"]
        if any(i not in lookup for i in ids):
            raise ItemError("chunk missing from the store")
        chunks = [lookup[i] for i in ids]
        calls = collect_calls()
        new_trace("ev-verify")
        t0 = time.perf_counter()
        out: dict = {
            "kinds": list(kinds(rec)),
            "fabricated_detected": None,
            "swapped_detected": None,
            "control_flagged": None,
        }
        out["fabricated_flagged_any"] = out["swapped_flagged_any"] = None

        def call(text: str):
            before = len(calls)
            res = vr(Answer(route="content", text=text), [], chunks)
            if len(calls) == before:  # verify.run fails open (also on QuotaError) without logging a call
                raise ItemError("verifier made no LLM call (quota/error swallowed by verify.run); re-run to retry")
            return res

        if "fabricated" in out["kinds"]:
            new_text, sent = fabricate(rec["text"])
            res = call(new_text)
            out["fabricated_sentence"] = sent
            out["fabricated_detected"] = sent in [s.strip() for s in res.unsupported_sentences]
            out["fabricated_flagged_any"] = not res.supported
        if "swapped" in out["kinds"]:
            sw = swap_citation(rec["text"], ids)
            if sw is None:
                out["swapped_skipped"] = "no cited sentence with an alternative passage"
            else:
                new_text, sent, tag = sw
                res = call(new_text)
                bad = {b.strip("[] ") for b in res.bad_citations}
                out["swapped_sentence"] = sent
                out["swapped_detected"] = sent in [s.strip() for s in res.unsupported_sentences] or tag in bad
                out["swapped_flagged_any"] = not res.supported
        if control:
            out["control_flagged"] = not call(rec["text"]).supported
        out["llm_calls"] = calls
        out["latency_s"] = round(time.perf_counter() - t0, 3)
        out["question"] = rec.get("question")
        return out

    return fn


def verify_targets(
    store: RunStore, split: str, limit: int | None, preset: bool
) -> tuple[list[dict], Callable[[dict], tuple[str, ...]]]:
    """Answered items eligible for perturbation. Preset: persisted ids, alternating fabricated/swapped (1 call each)."""
    elig = sorted(
        (r for r in store.load("answer", split) if r.get("set") == "qa" and verify_eligible(r)), key=lambda r: r["id"]
    )
    if not preset:
        return (elig[:limit] if limit else elig), lambda r: ("fabricated", "swapped")
    p = store.dir / "sample.json"
    sample = read_json(p) or {}
    ids = sample.get("verify") or []
    if not ids or not set(ids) <= {r["id"] for r in elig}:
        ids = [r["id"] for r in pick_spread(elig, PRESET_SMALL["verify"], random.Random(f"{SEED}-verify"), "course")]
        ids.sort()
        write_json(p, {**sample, "verify": ids})
    items = [r for r in elig if r["id"] in ids]
    kind = {i: ("fabricated",) if n % 2 == 0 else ("swapped",) for n, i in enumerate(ids)}
    return items, lambda r: kind[r["id"]]


# ------------------------------------------------------------------ planning
def calls_per_item(kind: str, conf: dict | None = None) -> tuple[int, int]:
    """(typical, maximum) free-model calls per item. Cached calls cost nothing, so this is an upper estimate."""
    c = conf or cfg()
    pipe = c.get("pipeline") or {}
    rewrite = 0 if pipe.get("merged_router", True) else 1
    verify = 1 if pipe.get("verify", False) else 0
    if kind == "router":
        return 1, 1
    if kind == "qa":  # router(+rewrite) + generate (+verify); max adds a borderline gate call and one regenerate round
        typ = 1 + rewrite + 1 + verify
        return typ, typ + 1 + (2 if verify else 0)
    if kind == "unanswerable":  # usually abstains at the gate: router(+rewrite); max = passes the gate and generates
        typ = 1 + rewrite
        return typ, typ + 1 + 1
    if kind == "logistics":
        return 2, 2
    raise ValueError(kind)


def plan_lines(counts: dict[str, int], verify_calls: int, conf: dict | None = None) -> tuple[list[str], int, int]:
    """counts = remaining items per kind (router/qa/unanswerable/logistics)."""
    lines, typ_t, max_t = [], 0, 0
    for kind in ("router", "qa", "unanswerable", "logistics"):
        n = counts.get(kind, 0)
        if not n and kind not in counts:
            continue
        t, m = calls_per_item(kind, conf)
        lines.append(f"  {kind:<13} {n:>4} items x {t} typical (max {m}) = {n * t} (max {n * m})")
        typ_t, max_t = typ_t + n * t, max_t + n * m
    if verify_calls:
        lines.append(f"  {'verify':<13} {verify_calls} calls (perturbation test, 1 per perturbation)")
        typ_t, max_t = typ_t + verify_calls, max_t + verify_calls
    return lines, typ_t, max_t


def print_plan(lines: list[str], typ: int, mx: int) -> None:
    print("Planned LLM calls (free model; items already done in this run are skipped, cached calls cost nothing):")
    print("\n".join(lines) if lines else "  (none: no LLM components selected)")
    print(f"  TOTAL ~{typ} (max {mx}).  Caveat: the free quota is ~50 requests/day per key, shared with anything else")
    print(
        "  you ran today; if it runs out the harness stops and tells you how to resume (same command, or another key)."
    )


# ------------------------------------------------------------------ orchestration
def sub_run(module: str, args: list[str]) -> bool:
    if not (ROOT / "eval" / f"{module.rsplit('.', 1)[-1]}.py").exists():
        print(f"[{module}] not found, skipped")
        return False
    r = subprocess.run([sys.executable, "-m", module, *args], cwd=ROOT)
    if r.returncode != 0:
        print(f"[{module}] exited with {r.returncode}")
    return r.returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--component", required=True, choices=["router", "gate", "answer", "logistics", "verify", "e2e", "all"]
    )
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--limit", type=int, help="cap items per gold set (ignored with --preset)")
    ap.add_argument(
        "--gold", type=Path, help="gold file for a single-set component (router/logistics; QA for answer/gate)"
    )
    ap.add_argument("--preset", choices=["small"], help="same-day budget preset (see module doc)")
    ap.add_argument("--run-id", help="resume/force a run id (default: <date>_<sha>_<config hash>)")
    ap.add_argument(
        "--verify-control", action="store_true", help="verify test: also verify the unperturbed answer (+1 call/item)"
    )
    ap.add_argument("--dry-run", action="store_true", help="print the call plan and exit")
    ap.add_argument("--no-score", action="store_true")
    a = ap.parse_args(argv)
    if a.gold and a.component in ("all", "e2e"):
        ap.error("--gold needs a single-set component")

    comp = a.component
    todo = ALL_ORDER if comp == "all" else (["answer", "logistics", "e2e"] if comp == "e2e" else [comp])
    run_id = a.run_id or runs.make_run_id() + ("_small" if a.preset else "")
    store = RunStore(run_id)
    preset = a.preset == "small"
    print(f"run_id: {run_id}   split: {a.split}   components: {', '.join(todo)}")

    # ---- gold (only the sets that are needed)
    need = {
        "router": ["router"],
        "gate": ["qa", "unanswerable"],
        "answer": ["qa", "unanswerable"],
        "logistics": ["logistics"],
    }
    sets = sorted({s for c in todo for s in need.get(c, [])})
    target = {"router": "router", "gate": "qa", "answer": "qa", "logistics": "logistics"}.get(comp)
    full_gold: dict[str, list[dict]] = {}
    gold_source: dict[str, str] = {}
    for s in sets:
        full_gold[s], gold_source[s] = load_gold(
            s, a.split, a.gold if s == target else None, None if preset else a.limit
        )
    if any("draft" in v for v in gold_source.values()):
        print("NOTE: gold = unreviewed draft for " + ", ".join(s for s, v in gold_source.items() if "draft" in v))

    chosen = dict(full_gold)  # gate always uses full_gold (all QA + unanswerable); the LLM components use `chosen`
    if preset and full_gold:
        llm_sets = {k: v for k, v in full_gold.items()}
        ids = preset_sample(llm_sets, store)
        for name in llm_sets:
            chosen[name] = [i for i in full_gold[name] if i["id"] in set(ids[name])]
        if "router" in full_gold and not (store.dir / "router_rest.jsonl").exists():
            rest = [i for i in full_gold["router"] if i["id"] not in set(ids["router"])]
            (store.dir / "router_rest.jsonl").write_text(
                "".join(
                    json.dumps({"id": i["id"], "question": i["question"], "gold_route": i["route"]}, ensure_ascii=False)
                    + "\n"
                    for i in rest
                ),
                encoding="utf-8",
            )
    store.write_meta(preset=a.preset, split=a.split, gold_source=gold_source, seed=SEED if preset else None)

    # ---- plan
    def remaining(component: str, items: list[dict]) -> int:
        done = store.done_ids(component, a.split)
        return len([i for i in items if i["id"] not in done])

    counts: dict[str, int] = {}
    if "router" in todo:
        counts["router"] = remaining("router", chosen["router"])
    if "answer" in todo or "e2e" in todo:
        counts["qa"] = remaining("answer", [i for i in chosen["qa"]])
        counts["unanswerable"] = remaining("answer", chosen["unanswerable"])
    if "logistics" in todo:
        counts["logistics"] = remaining("logistics", chosen["logistics"])
    v_calls = 0
    if "verify" in todo:
        n_v = PRESET_SMALL["verify"] if preset else (a.limit or 10)
        done_v = len(store.done_ids("verify", a.split))
        per = 1 if preset else 2 + int(a.verify_control)
        v_calls = max(0, n_v - done_v) * per
    lines, typ, mx = plan_lines(counts, v_calls)
    print_plan(lines, typ, mx)
    if a.dry_run:
        return 0

    # ---- execute
    try:
        for c in todo:
            if c == "gate":
                items = [*full_gold["qa"], *full_gold["unanswerable"]]
                s = run_items(store, "gate", a.split, items, gate_fn, "gate")
                print(f"gate: {s['n_done']}/{s['n_total']} (no LLM)")
            elif c == "retrieval":
                sub_run("eval.retrieval_eval", ["--split", a.split])
            elif c == "parser":
                sub_run("eval.parse_eval", [])
            elif c == "router":
                run_items(store, "router", a.split, chosen["router"], router_fn, "router")
            elif c == "answer":
                fn = make_pipeline_fn()
                run_items(store, "answer", a.split, chosen["qa"], fn, "qa")
                run_items(store, "answer", a.split, chosen["unanswerable"], fn, "unanswerable")
            elif c == "logistics":
                run_items(store, "logistics", a.split, chosen["logistics"], make_pipeline_fn(), "logistics")
            elif c == "verify":
                items, kinds = verify_targets(store, a.split, a.limit, preset)
                if not items:
                    print("verify: no eligible answered items; run --component answer first")
                    continue
                run_items(store, "verify", a.split, items, verify_fn_factory(kinds, a.verify_control), "verify")
    except QuotaStop as e:
        print(f"\n{e.message()}")
        return 2

    # ---- score
    if a.no_score:
        return 0
    from eval import report

    for c in [x for x in todo if x not in ("retrieval", "parser")]:
        if not store.load(c if c != "e2e" else "answer", a.split):
            continue
        res = score.score_component(run_id, c, a.split)
        print(f"wrote {score.write_result(res)}")
    print(f"summary: {report.write_summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
