import pytest

from app import config


@pytest.fixture(autouse=True)
def _tmp_traces(tmp_path_factory, monkeypatch):
    """Keep mock trace events out of the real logs/traces directory."""
    d = tmp_path_factory.mktemp("traces")
    monkeypatch.setitem(config.cfg()["paths"], "traces", str(d))
