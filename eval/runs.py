"""[EVAL] Shared run store: resumable per-item results under reports/eval/runs/<run_id>/<component>.jsonl.

run_id = <date>_<short git sha | "nogit">_<config hash of llm models + prompt versions + pipeline flags>.
Changing a prompt or a model starts a new run; an interrupted run with unchanged config resumes.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

from app.config import ROOT, cfg

RUNS_ROOT = ROOT / "reports" / "eval" / "runs"
EVAL_DIR = ROOT / "reports" / "eval"
# config sections that change pipeline behaviour (and therefore results)
_HASHED_SECTIONS = ("pipeline", "gate", "retrieval", "chat")


def prompt_versions(prompts_dir: Path | None = None) -> dict[str, str]:
    """{prompt name: version} for every prompts/*.md with a `version:` front-matter line."""
    d = prompts_dir or ROOT / cfg()["paths"]["prompts"]
    out: dict[str, str] = {}
    for p in sorted(d.glob("*.md")):
        m = re.match(r"---\s*\n(.*?)\n---", p.read_text(encoding="utf-8"), re.S)
        v = re.search(r"^version:\s*(\S+)", m.group(1), re.M) if m else None
        if v:
            out[p.stem] = v.group(1)
    return out


def config_snapshot(config: dict | None = None, versions: dict[str, str] | None = None) -> dict:
    c = config if config is not None else cfg()
    llm = c.get("llm", {})
    return {
        "models": llm.get("models", {}),
        "fallbacks": llm.get("fallbacks", {}),
        "prompts": versions if versions is not None else prompt_versions(),
        **{k: c.get(k) for k in _HASHED_SECTIONS},
    }


def config_hash(snapshot: dict | None = None) -> str:
    snap = snapshot if snapshot is not None else config_snapshot()
    return hashlib.sha256(json.dumps(snap, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:8]


def git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True
        )
        return r.stdout.strip() or "nogit"
    except Exception:  # noqa: BLE001 — not a repo / git missing
        return "nogit"


def make_run_id(today: date | None = None, sha: str | None = None, chash: str | None = None) -> str:
    return f"{(today or date.today()).isoformat()}_{sha or git_sha()}_{chash or config_hash()}"


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue  # a torn last line from an interrupted write: treat the item as not done
    return out


class RunStore:
    """Append-only per-component JSONL store for one run."""

    def __init__(self, run_id: str, root: Path | None = None):
        self.run_id = run_id
        self.dir = (root or RUNS_ROOT) / run_id

    def file(self, component: str) -> Path:
        return self.dir / f"{component}.jsonl"

    def load(self, component: str, split: str | None = None) -> list[dict]:
        recs = {r["id"]: r for r in read_jsonl(self.file(component)) if "id" in r}  # last write wins
        return [r for r in recs.values() if split is None or r.get("split") == split]

    def done_ids(self, component: str, split: str | None = None) -> set[str]:
        return {r["id"] for r in self.load(component, split)}

    def append(self, component: str, rec: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.file(component), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            f.flush()

    def append_error(self, component: str, rec: dict) -> None:
        """Items that failed for non-quota reasons; they are NOT 'done', so a re-run retries them."""
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / f"errors_{component}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def write_meta(self, **extra: object) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / "meta.json"
        meta = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        meta.update({"run_id": self.run_id, "config": config_snapshot(), **extra})
        p.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def meta(self) -> dict:
        p = self.dir / "meta.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def list_runs(root: Path | None = None) -> list[str]:
    """Run ids, oldest first (by directory mtime)."""
    r = root or RUNS_ROOT
    if not r.exists():
        return []
    return [d.name for d in sorted((x for x in r.iterdir() if x.is_dir()), key=lambda d: d.stat().st_mtime)]


def latest_run(component: str, split: str | None = None, root: Path | None = None) -> str | None:
    """Most recently written run that has records for `component` (and `split`)."""
    for rid in reversed(list_runs(root)):
        if RunStore(rid, root).load(component, split):
            return rid
    return None


def resolve_run(arg: str | None, component: str, split: str | None = None, root: Path | None = None) -> str:
    if arg and arg != "latest":
        return arg
    rid = latest_run(component, split, root)
    if rid is None:
        raise SystemExit(f"no run with component '{component}' found under {root or RUNS_ROOT}")
    return rid
