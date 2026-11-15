"""Eval harness: resumability, run ids, judgments, router/gate metrics, sampling, reports (mocks only, no LLM)."""

import csv
import json
from datetime import date

import pytest

from app import llm
from app.llm import QuotaError
from app.schemas import Answer, Chunk
from eval import judge_tasks, report, run, runs, score
from eval.runs import RunStore


@pytest.fixture
def tmp_eval(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(runs, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(score, "FIG_DIR", tmp_path / "figures")
    return tmp_path


# ------------------------------------------------------------------ run ids
def test_run_id_stable_and_config_sensitive():
    snap = {"models": {"fast": "a:free"}, "prompts": {"router": "1"}}
    assert runs.config_hash(snap) == runs.config_hash(dict(snap))
    changed = {"models": {"fast": "a:free"}, "prompts": {"router": "2"}}
    assert runs.config_hash(changed) != runs.config_hash(snap)
    rid = runs.make_run_id(date(2026, 11, 15), "abc1234", runs.config_hash(snap))
    assert rid == f"2026-11-15_abc1234_{runs.config_hash(snap)}"
    assert runs.make_run_id(sha="nogit").split("_")[1] == "nogit"


def test_prompt_versions_read(tmp_path):
    (tmp_path / "x.md").write_text("---\nversion: 7\n---\nbody")
    (tmp_path / "y.md").write_text("no front matter")
    assert runs.prompt_versions(tmp_path) == {"x": "7"}


# ------------------------------------------------------------------ resumability
def _items(n):
    return [{"id": f"it-{i}"} for i in range(n)]


def test_resume_after_quota(tmp_eval):
    store = RunStore("r1")
    calls = []

    def flaky(item):
        calls.append(item["id"])
        if len(calls) == 3:
            raise QuotaError("daily_free_limit", "m", "limit")
        return {"x": item["id"]}

    with pytest.raises(run.QuotaStop) as ei:
        run.run_items(store, "router", "dev", _items(5), flaky, log=lambda s: None)
    msg = ei.value.message()
    assert msg.startswith("Quota reached: 2/5 done") and "resume with the same command" in msg
    assert store.done_ids("router", "dev") == {"it-0", "it-1"}

    calls.clear()
    stats = run.run_items(store, "router", "dev", _items(5), lambda i: calls.append(i["id"]) or {}, log=lambda s: None)
    assert calls == ["it-2", "it-3", "it-4"]
    assert stats["n_skipped"] == 2 and stats["n_done"] == 5
    assert len(store.load("router", "dev")) == 5


def test_pipeline_swallowed_quota_is_detected_and_errors_not_stored(tmp_eval):
    store = RunStore("r2")

    def quota_pipeline(q, history):
        return Answer(
            route="content",
            text="x",
            debug={
                "error_kind": "quota",
                "quota": {
                    "kind": "daily_free_limit",
                    "model": "m",
                    "reset_at_iso": "2026-11-16T00:00:00+00:00",
                    "approximate": True,
                },
            },
        )

    items = [{"id": "qa-1", "question": "q"}]
    with pytest.raises(run.QuotaStop) as ei:
        run.run_items(store, "answer", "dev", items, run.make_pipeline_fn(quota_pipeline), "qa", log=lambda s: None)
    assert "2026-11-16 00:00 UTC" in ei.value.message()
    assert store.load("answer") == []

    def broken(q, history):
        return Answer(route="content", text="err", debug={"error": "ValueError('x')"})

    st = run.run_items(store, "answer", "dev", items, run.make_pipeline_fn(broken), "qa", log=lambda s: None)
    assert st["errors"] == 1 and store.load("answer") == []

    def fine(q, history):
        return Answer(
            route="content", text="ok", debug={"llm_calls": [{"model": "m", "cached": False, "latency_s": 1.0}]}
        )

    run.run_items(store, "answer", "dev", items, run.make_pipeline_fn(fine), "qa", log=lambda s: None)
    rec = store.load("answer", "dev")[0]
    assert rec["text"] == "ok" and rec["set"] == "qa" and rec["split"] == "dev" and rec["llm_calls"][0]["model"] == "m"


def test_torn_last_line_means_not_done(tmp_eval):
    store = RunStore("r3")
    store.append("router", {"id": "a", "split": "dev"})
    with open(store.file("router"), "a") as f:
        f.write('{"id": "b", "spl')
    assert store.done_ids("router") == {"a"}


# ------------------------------------------------------------------ preset sampling
def _router_gold():
    routes = score.ROUTES
    return [
        {"id": f"ro-{r}-{i}", "route": r, "question": f"q {r} {i}", "hard": i < 3, "course": None}
        for r in routes
        for i in range(8)
    ]


def test_router_sample_stratified_with_hard():
    s = run.sample_router(_router_gold(), 20, __import__("random").Random(1))
    assert len(s) == 20 and len({i["id"] for i in s}) == 20
    assert all(sum(i["route"] == r for i in s) == 4 for r in score.ROUTES)
    assert sum(bool(i["hard"]) for i in s) >= 4


def test_qa_sample_and_persistence(tmp_eval):
    qa = [
        {"id": f"qa-{t}-{i}-{c}", "type": t, "course": c}
        for t in ("single", "figure", "multi", "real")
        for i in range(6)
        for c in ("pok", "aks", "os")
    ]
    gold = {"qa": qa, "router": _router_gold()}
    store = RunStore("r4")
    a = run.preset_sample(gold, store)
    assert len(a["qa"]) == 12 and len(a["router"]) == 20
    types = [i["type"] for i in qa if i["id"] in set(a["qa"])]
    assert all(types.count(t) == 3 for t in ("single", "figure", "multi", "real"))
    b = run.preset_sample(gold, RunStore("r4"))
    assert a == b
    assert a == run.preset_sample(gold, RunStore("r4-other"))  # fixed seed, independent of the run dir


def test_plan_lines_budget():
    conf = {"pipeline": {"merged_router": True, "verify": False}}
    assert run.calls_per_item("router", conf) == (1, 1)
    assert run.calls_per_item("qa", conf)[0] == 2
    assert run.calls_per_item("logistics", conf) == (2, 2)
    lines, typ, mx = run.plan_lines({"router": 20, "qa": 12, "unanswerable": 5, "logistics": 5}, 5, conf)
    assert typ == 20 + 24 + 5 + 10 + 5 and mx > typ and len(lines) == 5
    assert run.calls_per_item("qa", {"pipeline": {"merged_router": False, "verify": True}})[0] == 4


# ------------------------------------------------------------------ router metrics
def test_router_metrics_toy():
    y_t = ["content", "content", "logistics", "off_topic", "navigation", "clarify"]
    y_p = ["content", "off_topic", "logistics", "off_topic", "content", "clarify"]
    m = score.router_metrics(y_t, y_p)
    assert m["accuracy"]["value"] == pytest.approx(4 / 6)
    assert m["false_reject_rate"]["value"] == pytest.approx(1 / 4)  # 4 in-domain items, one sent to off_topic
    assert m["per_class"]["content"]["recall"] == 0.5 and m["per_class"]["content"]["precision"] == 0.5
    assert m["confusion"]["matrix"][0][4] == 1
    assert 0 < m["macro_f1"] < 1


def test_score_router_with_baseline_and_png(tmp_eval):
    recs = []
    for i in range(12):
        route = "content" if i % 4 < 2 else "off_topic"
        q = f"поясни процес потік {i}" if route == "content" else f"рецепт борщу smalltalk {i}"
        recs.append(
            {
                "id": f"ro-{i:02d}",
                "question": q,
                "gold_route": route,
                "route": route,
                "latency_s": 1.0,
                "llm_calls": [{"model": "m", "cached": False}],
            }
        )
    store = RunStore("r5")
    for r in recs:
        store.append("router", {**r, "split": "dev"})
    res = score.score_component("r5", "router", "dev", fig_dir=tmp_eval / "figs")
    m = res["metrics"]
    assert m["accuracy"]["value"] == 1.0 and m["baseline"]["train_n"] == 6 and m["baseline"]["eval_n"] == 6
    assert m["models_served"] == {"m": 12}
    assert (tmp_eval / "figs" / "r5_router_confusion_dev.png").exists()


# ------------------------------------------------------------------ gate
def test_gate_sweep_toy(tmp_eval):
    scores = [0.9, 0.8, 0.6, 0.1, 0.05]
    ans = [True, True, True, False, False]
    sweep = score.gate_sweep(scores, ans)
    best = score.best_threshold(sweep)
    assert best["f1"] == 1.0 and 0.1 < best["threshold"] <= 0.6 and best["threshold"] == 0.11
    at = next(r for r in sweep if r["threshold"] == 0.0)
    assert at["recall"] == 0.0 and at["false_abstain_rate"] == 0.0
    top = next(r for r in sweep if r["threshold"] == 1.0)
    assert top["recall"] == 1.0 and top["false_abstain_rate"] == 1.0 and top["precision"] == pytest.approx(0.4)
    recs = [{"id": f"g{i}", "top_score": s, "answerable": a} for i, (s, a) in enumerate(zip(scores, ans, strict=True))]
    res = score.score_gate(recs, "rg", {"rerank_threshold": 0.15, "borderline": [0.05, 0.35]}, tmp_eval)
    assert res["frac_in_band"] == pytest.approx(2 / 5) and res["frac_in_band_unanswerable"] == 1.0
    assert (tmp_eval / "rg_gate_sweep.png").exists()


# ------------------------------------------------------------------ chunk equivalence
def test_chunk_match_slide_window():
    spans = {"d#5": ("d", 5, 5), "d#w4": ("d", 4, 6), "d#9": ("d", 9, 9), "e#5": ("e", 5, 5)}.get
    assert score.chunk_match("d#w4", "d#5", spans)
    assert score.chunk_match("d#5", "d#w4", spans)
    assert not score.chunk_match("d#9", "d#w4", spans)
    assert not score.chunk_match("e#5", "d#5", spans)
    assert score.cites_gold(["x#1", "d#w4"], ["d#5"], spans)
    assert score.default_span("zz_nonexistent#w7") == ("zz_nonexistent", 7, 7)


# ------------------------------------------------------------------ answer scoring + judgments
def _answer_recs():
    base = {"set": "qa", "split": "dev", "llm_calls": [], "latency_s": 2.0, "type": "single"}
    return [
        {
            **base,
            "id": "qa-1",
            "route": "content",
            "abstained": False,
            "text": "Відповідь [S1]",
            "citations": [{"tag": "S1", "chunk_id": "d#5", "doc_id": "d"}],
            "invalid_citations": [],
            "gold_chunk_ids": ["d#5"],
        },
        {
            **base,
            "id": "qa-2",
            "route": "content",
            "abstained": False,
            "text": "Інша [S9]",
            "citations": [],
            "invalid_citations": ["S9"],
            "gold_chunk_ids": ["d#7"],
        },
        {
            **base,
            "id": "qa-3",
            "route": "content",
            "abstained": True,
            "text": "Немає",
            "citations": [],
            "invalid_citations": [],
            "gold_chunk_ids": ["d#1"],
        },
        {
            **base,
            "id": "qa-4",
            "route": "off_topic",
            "abstained": False,
            "text": "off",
            "citations": [],
            "invalid_citations": [],
            "gold_chunk_ids": ["d#1"],
        },
        {
            **base,
            "id": "un-1",
            "set": "unanswerable",
            "route": "content",
            "abstained": True,
            "text": "Немає",
            "citations": [],
            "invalid_citations": [],
        },
        {
            **base,
            "id": "un-2",
            "set": "unanswerable",
            "route": "content",
            "abstained": False,
            "text": "вигадка",
            "citations": [],
            "invalid_citations": [],
        },
    ]


def _judgment(tid, correctness=5, kf=(True, True), supported=True, cit=True):
    return {
        "task_id": tid,
        "correctness": correctness,
        "key_fact_supported": list(kf),
        "claims": [{"text": "s", "supported": supported, "citations_ok": cit}],
        "language_ok": True,
        "abstain_correct": None,
        "notes": "",
    }


def test_score_answer_partial_judgments(tmp_eval):
    recs = _answer_recs()
    m = score.score_answer(recs, {"answer:qa-1": _judgment("answer:qa-1", 5)})
    qa = m["qa"]
    assert qa["route_correct"]["value"] == pytest.approx(3 / 4)
    assert qa["abstain_rate_on_answerable"]["value"] == pytest.approx(1 / 4)
    assert qa["citation_validity_rate"] == pytest.approx(0.5)
    assert qa["gold_chunk_cited_rate"]["value"] == pytest.approx(1 / 4)
    j = m["judged"]
    # qa-3 (abstained) and qa-4 (wrong route) are scored automatically as wrong; qa-2 is still pending
    assert j["n_scored"] == 3 and j["n_pending"] == 1 and j["n_llm_judged"] == 1
    assert j["correct_ge4_rate"]["value"] == pytest.approx(1 / 3)
    assert m["unanswerable"]["correct_abstain_rate"]["value"] == 0.5


def test_load_judgments_merges_batches_and_flags_invalid(tmp_eval):
    store = RunStore("r6")
    for r in _answer_recs():
        store.append(
            "answer",
            {
                **r,
                "debug": {"chunks_in_prompt": ["d#5"]},
                "reference_answer": "ref",
                "key_facts": ["a", "b"],
                "question": "q",
            },
        )
    p, n = judge_tasks.write_tasks(store, "answer", "dev", lambda cid: ("crumb", "t" * 3000))
    assert n == 2  # qa-1 and qa-2: the abstained / wrong-route items are not exported
    tasks = score.load_tasks(store, "answer")
    assert set(tasks) == {"answer:qa-1", "answer:qa-2"}
    t = tasks["answer:qa-1"]
    assert len(t["passages"][0]["text"]) == judge_tasks.PASSAGE_CHARS and t["passages"][0]["cited"]
    assert "gold_chunk_ids" not in t and "gold_chunk_ids" not in json.dumps(t)
    bad = {**_judgment("answer:qa-2"), "key_fact_supported": [True]}  # wrong length
    (store.dir / "judgments_answer_0.jsonl").write_text(
        json.dumps(_judgment("answer:qa-1", 4)) + "\n" + json.dumps(bad) + "\n"
    )
    (store.dir / "judgments_answer_1.jsonl").write_text(
        json.dumps(_judgment("answer:qa-1", 3)) + "\n"
    )  # later file wins
    j, errs = score.load_judgments(store, "answer")
    assert j["answer:qa-1"]["correctness"] == 3 and "answer:qa-2" not in j
    assert len(errs) == 1 and "key_fact_supported has 1" in errs[0]
    res = score.score_component("r6", "answer", "dev")
    assert res["metrics"]["judged"]["n_pending"] == 1


def test_validate_judgment_shapes():
    assert score.validate_judgment(_judgment("t")) == []
    assert score.validate_judgment({**_judgment("t"), "correctness": 6})
    assert score.validate_judgment({**_judgment("t"), "correctness": 3.5})
    assert score.validate_judgment({**_judgment("t"), "language_ok": "yes"})
    assert score.validate_judgment({"correctness": 3})


def test_calibration_csv_and_kappa(tmp_eval):
    store = RunStore("r7")
    for i in range(6):
        store.append(
            "answer",
            {
                "id": f"qa-{i}",
                "split": "dev",
                "set": "qa",
                "route": "content",
                "abstained": False,
                "text": f"a{i} [S1]",
                "citations": [{"tag": "S1", "chunk_id": "d#1", "doc_id": "d"}],
                "question": "q",
                "reference_answer": "r",
                "key_facts": ["a"],
                "debug": {},
            },
        )
    judge_tasks.write_tasks(store, "answer", "dev", lambda cid: ("c", "text"))
    lines = [json.dumps(_judgment(f"answer:qa-{i}", 1 + i % 5, kf=(True,), supported=i % 2 == 0)) for i in range(6)]
    (store.dir / "judgments_answer_0.jsonl").write_text("\n".join(lines) + "\n")
    p = judge_tasks.write_calibration(store, "answer", 5, out_dir=tmp_eval)
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5 and all(r["human_correctness"] == "" for r in rows)
    assert score.calibration_stats(p)["kappa_faithful"] is None
    for r in rows:  # a human who agrees on faithfulness and roughly on correctness
        r["human_faithful"] = r["judge_faithful"]
        r["human_correctness"] = str(min(5, int(r["judge_correctness"]) + 1))
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    st = score.calibration_stats(p)
    assert st["n_faithful"] == 5 and st["kappa_faithful"] == pytest.approx(1.0)
    assert st["spearman_correctness"] > 0.8


# ------------------------------------------------------------------ logistics / e2e
def test_logistics_and_e2e(tmp_eval):
    ans = _answer_recs()
    lo = [
        {
            "id": "lo-1",
            "split": "dev",
            "set": "logistics",
            "route": "logistics",
            "abstained": False,
            "text": "x [S1]",
            "citations": [{"doc_id": "syl", "chunk_id": "syl#1", "tag": "S1"}],
            "gold_doc_ids": ["syl"],
            "llm_calls": [],
        },
        {
            "id": "lo-2",
            "split": "dev",
            "set": "logistics",
            "route": "content",
            "abstained": False,
            "text": "y",
            "citations": [],
            "gold_doc_ids": ["syl"],
            "llm_calls": [],
        },
    ]
    m = score.score_logistics(
        lo, {"logistics:lo-1": _judgment("logistics:lo-1", 4), "logistics:lo-2": _judgment("logistics:lo-2", 5)}
    )
    assert m["route_correct"]["value"] == 0.5 and m["source_doc_cited"]["value"] == 0.5
    e = score.score_e2e(
        ans,
        lo,
        {"answer:qa-1": _judgment("answer:qa-1", 4)},
        {"logistics:lo-1": _judgment("logistics:lo-1", 4), "logistics:lo-2": _judgment("logistics:lo-2", 5)},
    )
    # qa-1 ok, qa-2 pending, qa-3/qa-4 fail, un-1 ok, un-2 fail, lo-1 ok, lo-2 wrong route
    assert e["n"] == 8 and e["n_pending_judgment"] == 1
    assert e["success_rate"]["value"] == pytest.approx(3 / 7)


# ------------------------------------------------------------------ verify perturbation
def test_perturbations():
    t, s = run.fabricate("Перше речення. [S1]")
    assert t.endswith(s) and s.endswith("[S1]") and t.count("\n") == 1
    out = run.swap_citation("Мікроядро мінімальне. [S1] Ще факт. [S2]", ["a#1", "b#2", "c#3"])
    assert out is not None
    new_text, sent, tag = out
    assert tag == "S3" or tag == "S2"  # a passage not cited by that sentence, preferably of another document
    assert sent in new_text and "[S1]" not in sent
    assert run.swap_citation("Єдине речення. [S1]", ["a#1"]) is None


def test_verify_fn_detection_and_failopen(tmp_eval):
    from app.schemas import VerifyResult

    chunk = Chunk(
        chunk_id="a#1", doc_id="a", courses=["os"], doc_type="lecture", breadcrumb="b", text="t", search_text="t"
    )
    chunk2 = chunk.model_copy(update={"chunk_id": "b#2", "doc_id": "b"})
    lookup = {"a#1": chunk, "b#2": chunk2}
    rec = {"id": "qa-1", "question": "q", "text": "Факт. [S1]", "debug": {"chunks_in_prompt": ["a#1", "b#2"]}}

    def good(answer, hits, chunks):
        llm._calls.get().append({"step": "verify", "model": "m", "cached": False})
        lines = [ln for ln in answer.text.split("\n") if ln.strip()]
        return VerifyResult(
            supported=len(lines) == 1 and "S2" not in answer.text,
            unsupported_sentences=[ln for ln in lines if "1987" in ln or "S2" in ln],
        )

    fn = run.verify_fn_factory(lambda r: ("fabricated", "swapped"), True, good, lookup)
    out = fn(rec)
    assert out["fabricated_detected"] is True and out["swapped_detected"] is True and out["control_flagged"] is False
    assert len(out["llm_calls"]) == 3

    def swallowed(answer, hits, chunks):  # verify.run fails open without making a call
        return VerifyResult(supported=True)

    with pytest.raises(run.ItemError):
        run.verify_fn_factory(lambda r: ("fabricated",), False, swallowed, lookup)(rec)
    m = score.score_verify(
        [
            {
                "id": "a",
                "fabricated_detected": True,
                "fabricated_flagged_any": True,
                "swapped_detected": None,
                "swapped_flagged_any": None,
                "control_flagged": None,
            }
        ]
    )
    assert m["fabricated_detected"]["value"] == 1.0 and m["swapped_detected"]["n"] == 0


# ------------------------------------------------------------------ gold fallback + report
def test_gold_fallback_to_review(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    (tmp_path / "review").mkdir()
    (tmp_path / "review" / "qa.jsonl").write_text('{"id": "qa-001"}\n')
    p, src = run.gold_path("qa", "dev")
    assert src == "unreviewed draft" and p.name == "qa.jsonl"
    with pytest.raises(SystemExit):
        run.gold_path("qa", "test")
    (tmp_path / "qa_dev.jsonl").write_text('{"id": "qa-002"}\n')
    assert run.gold_path("qa", "dev")[1] == "reviewed"


def test_report_summary_and_history(tmp_eval):
    store = RunStore("r8_small")
    store.write_meta(preset="small", gold_source={"router": "unreviewed draft"})
    for i in range(4):
        store.append(
            "router",
            {
                "id": f"ro-{i}",
                "split": "dev",
                "question": "q",
                "gold_route": "content",
                "route": "content" if i else "off_topic",
                "latency_s": 1.0,
                "llm_calls": [],
            },
        )
    out = report.write_summary(out=tmp_eval / "summary.md")
    txt = out.read_text(encoding="utf-8")
    assert "small-sample run: differences within CI are not significant" in txt
    assert "unreviewed draft" in txt and "r8_small" in txt and "accuracy" in txt
    res = report.collect()
    rows = report.append_history(res, "first run", path=tmp_eval / "history.md")
    assert rows and "n/a → 0.750" in rows[0]
    rows2 = report.append_history(res, "second", path=tmp_eval / "history.md")
    assert "0.750 → 0.750" in rows2[0]


# ------------------------------------------------------------------ congestion: wait and retry
def test_backoff_schedule():
    w = run.backoff_schedule()
    assert w[:5] == [30, 60, 120, 240, 240] and sum(w) <= 900 < sum(w) + 240


def test_rate_limited_waits_then_succeeds(tmp_eval, monkeypatch):
    slept = []
    monkeypatch.setattr(run, "sleep", slept.append)
    store = RunStore("c1")
    n = {"i": 0}

    def fn(item):
        n["i"] += 1
        if n["i"] <= 2:
            raise QuotaError("rate_limited", "ling:free", "429")
        if n["i"] == 3:
            raise run.TransientError("router fell back")
        return {"ok": 1}

    st = run.run_items(store, "router", "dev", _items(1), fn, log=lambda s: None)
    assert slept == [30, 60, 120] and st["n_done"] == 1 and store.done_ids("router", "dev") == {"it-0"}


def test_gives_up_on_item_and_continues(tmp_eval, monkeypatch):
    slept = []
    monkeypatch.setattr(run, "sleep", slept.append)
    store = RunStore("c2")
    lines = []

    def fn(item):
        if item["id"] == "it-0":
            raise QuotaError("rate_limited", "m", "429")
        return {}

    st = run.run_items(store, "router", "dev", _items(2), fn, log=lines.append)
    assert slept == run.backoff_schedule() and st["errors"] == 1
    assert store.done_ids("router", "dev") == {"it-1"}
    assert (store.dir / "errors_router.jsonl").exists() and any("gave up" in ln for ln in lines)
    assert sum("waiting" in ln for ln in lines) == len(slept)


@pytest.mark.parametrize("kind", ["daily_free_limit", "auth", "no_credits"])
def test_hard_quota_kinds_stop_without_waiting(tmp_eval, monkeypatch, kind):
    monkeypatch.setattr(run, "sleep", lambda s: pytest.fail("must not wait"))

    def fn(item):
        raise QuotaError(kind, "m", "x")

    with pytest.raises(run.QuotaStop) as ei:
        run.run_items(RunStore("c3"), "router", "dev", _items(1), fn, log=lambda s: None)
    msg = ei.value.message()
    assert ("daily limit" in msg) if kind == "daily_free_limit" else ("key problem" in msg)


def test_stop_message_rate_limited():
    assert "providers congested" in run.QuotaStop("router", 1, 20, "x", "rate_limited").message()
