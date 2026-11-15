"""The only place that talks to LLM/VLM APIs (OpenRouter, OpenAI-compatible).

Features: prompt files with versions, disk cache, retries + fallback models, JSON parsing,
image inputs, and JSONL tracing of every call (grouped by trace id).
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import openai
from openai import OpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import cfg, path

# ---------------------------------------------------------------- tracing
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def new_trace(tag: str = "q") -> str:
    tid = f"{tag}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    _trace_id.set(tid)
    return tid


def current_trace() -> str:
    return _trace_id.get()


def trace_event(step: str, **data: Any) -> None:
    """Append one event to logs/traces/<date>.jsonl (no-op for empty trace id)."""
    tid = _trace_id.get()
    if not tid:
        return
    d = path("traces")
    d.mkdir(parents=True, exist_ok=True)
    rec = {"trace_id": tid, "ts": time.time(), "step": step, **data}
    with open(d / f"{datetime.now():%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- prompts
@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    def render(self, **kw: Any) -> tuple[str, str]:
        def sub(t: str) -> str:
            for k, v in kw.items():
                t = t.replace("{{" + k + "}}", str(v))
            left = re.findall(r"\{\{(\w+)\}\}", t)
            if left:
                raise KeyError(f"prompt {self.name}: unfilled vars {left}")
            return t

        return sub(self.system), sub(self.user)


def load_prompt(name: str) -> Prompt:
    """prompts/<name>.md: front matter `version: X`, then `<<<SYSTEM>>>` and `<<<USER>>>` blocks."""
    raw = (path("prompts") / f"{name}.md").read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if not m:
        raise ValueError(f"prompt {name} lacks front matter")
    meta = yaml_lite(m.group(1))
    body = raw[m.end() :]
    sys_part, _, user_part = body.partition("<<<USER>>>")
    sys_part = sys_part.replace("<<<SYSTEM>>>", "").strip()
    return Prompt(name, str(meta["version"]), sys_part, user_part.strip())


def yaml_lite(s: str) -> dict[str, str]:
    return {k.strip(): v.strip() for k, _, v in (ln.partition(":") for ln in s.splitlines() if ":" in ln)}


# ---------------------------------------------------------------- client
_client: OpenAI | None = None
_key_override: str | None = None  # runtime key from the UI; memory only, never written anywhere


def _api_key() -> str:
    c = cfg()["llm"]
    key = _key_override or os.environ.get(c["api_key_env"])
    if not key:
        raise QuotaError("auth", "-", f"{c['api_key_env']} is not set (copy .env.example to .env)")
    return key


def set_api_key(key: str | None) -> None:
    """Switch the API key at runtime (UI). None/empty reverts to the environment key. Memory only."""
    global _client, _key_override
    _key_override = (key or "").strip() or None
    _client = None


def client() -> OpenAI:
    global _client
    if _client is None:
        c = cfg()["llm"]
        _client = OpenAI(base_url=c["base_url"], api_key=_api_key(), timeout=c["timeout_s"], max_retries=0)
    return _client


def key_status() -> dict:
    """GET {base_url}/key: label/limit/usage/is_free_tier (no secrets), or {"error": ...}."""
    try:
        req = urllib.request.Request(
            f"{cfg()['llm']['base_url']}/key", headers={"Authorization": f"Bearer {_api_key()}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 — fixed https base_url from config
            d = json.load(r).get("data", {})
        label = str(d.get("label", ""))
        return {
            "label": label[:4] + "…" + label[-4:] if len(label) > 12 else label,
            "limit": d.get("limit"),
            "usage": d.get("usage"),
            "is_free_tier": d.get("is_free_tier"),
        }
    except QuotaError as e:
        return {"error": e.message}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


# ---------------------------------------------------------------- quota-aware errors
class QuotaError(RuntimeError):
    """Quota / rate-limit / key problem. kind: daily_free_limit | rate_limited | no_credits | auth."""

    def __init__(
        self, kind: str, model: str, message: str = "", reset_at: datetime | None = None, approximate: bool = False
    ):
        super().__init__(f"{kind} ({model}): {message}")
        self.kind, self.model, self.message = kind, model, message
        self.reset_at, self.approximate = reset_at, approximate


class EmptyCompletion(RuntimeError):
    """The model returned no content (e.g. reasoning ate max_tokens): go to the next fallback, don't retry."""


_DAILY_RE = re.compile(r"free-models-per-day|per[- ]day|daily", re.I)
_MINUTE_RE = re.compile(r"per[- ]min", re.I)


def next_utc_midnight(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def classify_error(status: int, body: Any, headers: Any, model: str, message: str = "") -> QuotaError | None:
    """Map an HTTP failure to a QuotaError (None = not quota-related)."""
    text = f"{message} {json.dumps(body, ensure_ascii=False, default=str) if body else ''}"
    if status == 401:
        return QuotaError("auth", model, text.strip()[:300])
    if status == 402:
        return QuotaError("no_credits", model, text.strip()[:300])
    if status != 429:
        return None
    daily = bool(_DAILY_RE.search(text)) and not (_MINUTE_RE.search(text) and "free-models-per-day" not in text)
    if not daily:
        return QuotaError("rate_limited", model, text.strip()[:300])
    reset_at, approx = None, True
    raw = (headers or {}).get("X-RateLimit-Reset") or (headers or {}).get("x-ratelimit-reset")
    if raw:
        try:
            reset_at, approx = datetime.fromtimestamp(int(float(raw)) / 1000, UTC), False
        except (ValueError, OverflowError, OSError):
            reset_at = None
    if reset_at is None:
        reset_at, approx = next_utc_midnight(), True
    return QuotaError("daily_free_limit", model, text.strip()[:300], reset_at, approx)


def _from_openai(e: Exception, model: str) -> QuotaError | None:
    if isinstance(e, openai.APIStatusError):
        try:
            headers = dict(e.response.headers)
        except Exception:  # noqa: BLE001
            headers = {}
        return classify_error(e.status_code, e.body, headers, model, str(e))
    return None


def _retryable(e: BaseException) -> bool:
    if isinstance(e, QuotaError | EmptyCompletion):
        return False
    if isinstance(e, openai.APIStatusError):
        return e.status_code >= 500 or e.status_code == 408
    return isinstance(e, openai.APIConnectionError)  # includes timeouts


_overrides: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("model_overrides", default=None)


@contextlib.contextmanager
def override_models(**role_to_model: str):
    """Temporarily use other models for roles (model comparison): `with override_models(vlm="x/y"): ...`.
    Overridden roles get no fallbacks, so a failing candidate shows up as a failure, not as another model's output."""
    token = _overrides.set({**(_overrides.get() or {}), **role_to_model})
    try:
        yield
    finally:
        _overrides.reset(token)


def model_for(role: str) -> list[str]:
    ov = _overrides.get() or {}
    if role in ov:
        return [ov[role]]
    c = cfg()["llm"]
    return [c["models"][role], *c.get("fallbacks", {}).get(role, [])]


def image_part(png_bytes: bytes) -> dict:
    b64 = base64.b64encode(png_bytes).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


@dataclass
class LLMResult:
    text: str
    model: str
    cached: bool
    latency_s: float
    usage: dict


def _cache_file(key: str) -> Path:
    d = path("cache") / "llm" / key[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


@retry(
    stop=stop_after_attempt(cfg()["llm"]["max_retries"]),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _call(
    model: str, messages: list[dict], temperature: float, max_tokens: int, json_mode: bool, reasoning: dict | None
) -> Any:
    kw: dict[str, Any] = {}
    if reasoning:
        kw["extra_body"] = {"reasoning": reasoning}
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    try:
        resp = client().chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, **kw
        )
    except openai.APIStatusError as e:
        qe = _from_openai(e, model)
        if qe is not None:
            raise qe from None
        raise
    if not resp.choices or not (resp.choices[0].message.content or "").strip():
        raise EmptyCompletion(f"empty completion from {model}")
    return resp


# per-request log of which model served which call (set by pipeline.answer.run)
_calls: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("llm_calls", default=None)


def collect_calls() -> list[dict]:
    """Start recording {step, model, cached, latency_s} for every complete() call in this context."""
    lst: list[dict] = []
    _calls.set(lst)
    return lst


def complete(
    prompt: Prompt,
    role: str,
    *,
    images: list[bytes] | None = None,
    history: list[dict] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1200,
    json_mode: bool = False,
    use_cache: bool = True,
    step: str | None = None,
    **vars: Any,
) -> LLMResult:
    """Render `prompt` with `vars`, call the model for `role` (with fallbacks), cache and trace."""
    system, user = prompt.render(**vars)
    user_content: Any = user
    if images:
        user_content = [{"type": "text", "text": user}, *[image_part(b) for b in images]]
    messages = [
        {"role": "system", "content": system},
        *(history or []),
        {"role": "user", "content": user_content},
    ]

    img_hash = hashlib.sha256(b"".join(images or [])).hexdigest()
    reasoning = cfg()["llm"].get("reasoning", {}).get(role)
    ov = _overrides.get() or {}
    if role in ov and not ov[role].startswith("google/"):
        reasoning = None  # "minimal" effort is a Gemini workaround; other candidates run with provider defaults
    max_tokens = max(max_tokens, int(cfg()["llm"].get("min_max_tokens", 0)))
    last_err: Exception | None = None
    quota: dict[str, QuotaError] = {}
    for model in model_for(role):
        key_src = json.dumps(
            [model, prompt.name, prompt.version, system, history, user, img_hash, temperature, json_mode, reasoning],
            ensure_ascii=False,
        )
        key = hashlib.sha256(key_src.encode()).hexdigest()
        cf = _cache_file(key)
        t0 = time.time()
        if use_cache and cf.exists():
            rec = json.loads(cf.read_text(encoding="utf-8"))
            res = LLMResult(rec["text"], model, True, 0.0, rec.get("usage", {}))
        else:
            try:
                resp = _call(model, messages, temperature, max_tokens, json_mode, reasoning)
            except QuotaError as e:
                last_err = e
                quota.setdefault(e.kind, e)
                trace_event("llm_error", prompt=prompt.name, model=model, kind=e.kind, error=e.message[:300])
                if e.kind != "rate_limited":
                    break  # key/account-wide problem: other models would fail the same way
                continue  # upstream congestion: next fallback immediately
            except Exception as e:  # noqa: BLE001 — try next fallback model
                last_err = e
                trace_event("llm_error", prompt=prompt.name, model=model, error=repr(e)[:500])
                continue
            usage = resp.usage.model_dump() if resp.usage else {}
            text = resp.choices[0].message.content
            res = LLMResult(text, model, False, time.time() - t0, usage)
            cf.write_text(json.dumps({"text": text, "usage": usage, "model": model}, ensure_ascii=False))
        trace_event(
            step or f"llm:{prompt.name}",
            prompt=prompt.name,
            prompt_version=prompt.version,
            model=model,
            cached=res.cached,
            latency_s=round(res.latency_s, 3),
            usage=res.usage,
            input=user[:4000],
            output=res.text[:4000],
        )
        log = _calls.get()
        if log is not None:
            log.append(
                {
                    "step": step or prompt.name,
                    "model": model,
                    "cached": res.cached,
                    "latency_s": round(res.latency_s, 2),
                }
            )
        return res
    for kind in ("auth", "no_credits", "daily_free_limit", "rate_limited"):
        if kind in quota:
            raise quota[kind]
    raise RuntimeError(f"all models failed for role={role}: {last_err!r}")


def parse_json(text: str) -> Any:
    """Parse JSON, tolerating ```json fences and leading prose."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def complete_json(prompt: Prompt, role: str, **kw: Any) -> tuple[Any, LLMResult]:
    """complete() in JSON mode; one retry without cache if parsing fails."""
    res = complete(prompt, role, json_mode=True, **kw)
    try:
        return parse_json(res.text), res
    except (json.JSONDecodeError, ValueError):
        kw["use_cache"] = False
        kw["temperature"] = 0.3
        res = complete(prompt, role, json_mode=True, **kw)
        return parse_json(res.text), res
