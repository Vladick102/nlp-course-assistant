"""Quota-aware LLM errors: classification, no retry, fallbacks, min_max_tokens (all mocked)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import openai
import pytest

from app import llm
from app.llm import Prompt, QuotaError, classify_error

DAILY = {"error": {"message": "Rate limit exceeded: free-models-per-day. Add credits", "code": 429}}
UPSTREAM = {"error": {"message": "m is temporarily rate-limited upstream. Please retry shortly.", "code": 429}}


def test_classify_auth_and_credits():
    assert classify_error(401, {}, {}, "m").kind == "auth"
    assert classify_error(402, {}, {}, "m").kind == "no_credits"
    assert classify_error(500, {}, {}, "m") is None


def test_classify_daily_with_header():
    ms = int(datetime(2026, 11, 16, tzinfo=UTC).timestamp() * 1000)
    e = classify_error(429, DAILY, {"X-RateLimit-Reset": str(ms)}, "m")
    assert e.kind == "daily_free_limit" and e.reset_at == datetime(2026, 11, 16, tzinfo=UTC) and not e.approximate


def test_classify_daily_without_header_is_next_midnight():
    e = classify_error(429, DAILY, {}, "m")
    assert e.kind == "daily_free_limit" and e.approximate
    assert (e.reset_at.hour, e.reset_at.minute) == (0, 0) and e.reset_at > datetime.now(UTC)


def test_classify_upstream_429_is_rate_limited():
    assert classify_error(429, UPSTREAM, {}, "m").kind == "rate_limited"
    assert classify_error(429, {"error": {"message": "free-models-per-min exceeded"}}, {}, "m").kind == "rate_limited"


def _status_error(status, body, headers=None):
    resp = SimpleNamespace(request=None, status_code=status, headers=headers or {})
    return openai.APIStatusError("boom", response=resp, body=body)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Fake client whose responses are scripted per model; counts requests."""
    st = SimpleNamespace(script={}, calls=[], max_tokens=[])

    def create(model, messages, temperature, max_tokens, **kw):
        st.calls.append(model)
        st.max_tokens.append(max_tokens)
        r = st.script[model]
        r = r.pop(0) if isinstance(r, list) else r
        if isinstance(r, Exception):
            raise r
        msg = SimpleNamespace(content=r)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "client", lambda: fake_client)
    monkeypatch.setattr(llm, "model_for", lambda role: ["a:free", "b:free", "c:free"])
    monkeypatch.setattr(llm, "_cache_file", lambda key: tmp_path / f"{key}.json")
    monkeypatch.setattr(llm._call.retry, "wait", lambda *a, **k: 0)
    monkeypatch.setattr(llm._call.retry, "sleep", lambda s: None)
    return st


P = Prompt("t", "1", "sys", "user")


def test_daily_limit_not_retried_and_stops(fake):
    fake.script = {"a:free": _status_error(429, DAILY)}
    with pytest.raises(QuotaError) as ei:
        llm.complete(P, "fast")
    assert ei.value.kind == "daily_free_limit"
    assert fake.calls == ["a:free"]  # no retry, no fallback attempts


def test_auth_not_retried(fake):
    fake.script = {"a:free": _status_error(401, {"error": {"message": "bad key"}})}
    with pytest.raises(QuotaError) as ei:
        llm.complete(P, "fast")
    assert ei.value.kind == "auth" and fake.calls == ["a:free"]


def test_upstream_429_falls_back_immediately(fake):
    fake.script = {"a:free": _status_error(429, UPSTREAM), "b:free": "ok"}
    res = llm.complete(P, "fast")
    assert res.text == "ok" and res.model == "b:free" and fake.calls == ["a:free", "b:free"]


def test_all_rate_limited_raises_quota(fake):
    fake.script = {m: _status_error(429, UPSTREAM) for m in ("a:free", "b:free", "c:free")}
    with pytest.raises(QuotaError) as ei:
        llm.complete(P, "fast")
    assert ei.value.kind == "rate_limited" and len(fake.calls) == 3


def test_empty_content_goes_to_next_model(fake):
    fake.script = {"a:free": "  ", "b:free": "fine"}
    res = llm.complete(P, "fast")
    assert res.model == "b:free" and fake.calls == ["a:free", "b:free"]


def test_transient_5xx_is_retried(fake):
    fake.script = {"a:free": [_status_error(503, {}), "recovered"]}
    assert llm.complete(P, "fast").text == "recovered"
    assert fake.calls == ["a:free", "a:free"]


def test_min_max_tokens(fake, monkeypatch):
    fake.script = {"a:free": "ok"}
    llm.complete(P, "fast", max_tokens=100)
    assert fake.max_tokens == [llm.cfg()["llm"]["min_max_tokens"]]
    fake.script = {"a:free": "ok2"}
    llm.complete(P, "fast", max_tokens=5000, use_cache=False)
    assert fake.max_tokens[-1] == 5000


def test_calls_are_recorded(fake):
    fake.script = {"a:free": "ok"}
    log = llm.collect_calls()
    llm.complete(P, "fast", step="s1")
    assert log[0]["step"] == "s1" and log[0]["model"] == "a:free"


def test_set_api_key_resets_client(monkeypatch):
    monkeypatch.setattr(llm, "_client", object())
    llm.set_api_key("sk-test")
    assert llm._client is None and llm._api_key() == "sk-test"
    llm.set_api_key(None)
    assert llm._key_override is None
