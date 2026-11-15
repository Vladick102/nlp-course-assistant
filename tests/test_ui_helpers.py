"""Pure UI helpers (no Streamlit session needed)."""

from __future__ import annotations

from datetime import UTC, datetime

from app import ui
from app.schemas import Citation, Turn


def _cit(tag, cid):
    return Citation(tag=tag, chunk_id=cid, doc_id="d", page_start=3, page_end=3, label="L")


def test_render_tags_numbers_and_links():
    cits = [_cit("S1", "a"), _cit("S2", "b")]
    out = ui.render_tags("Так [S1], ще [S2][S1]. Невідомо [S9].", cits, {"S1": "u1", "S2": "u2"})
    assert out == "Так [¹](u1), ще [²](u2)[¹](u1). Невідомо ."


def test_render_tags_without_link_is_plain_superscript():
    assert ui.render_tags("x [S1]", [_cit("S1", "a")]) == "x ¹"


def test_superscript_multi_digit():
    assert ui.superscript(12) == "¹²"


def test_format_reset_exact_and_approximate():
    iso = datetime(2026, 11, 16, 0, 0, tzinfo=UTC).isoformat()
    exact, approx = ui.format_reset(iso, False), ui.format_reset(iso, True)
    assert approx == f"приблизно {exact}" and ":" in exact
    assert ui.format_reset(None, True) is None


def test_quota_messages():
    iso = datetime(2026, 11, 16, 0, 0, tzinfo=UTC).isoformat()
    head, detail = ui.quota_message({"kind": "daily_free_limit", "reset_at_iso": iso, "approximate": True})
    assert head == "Вичерпано денний ліміт безкоштовних запитів OpenRouter." and "приблизно" in detail
    assert "перевантажені" in ui.quota_message({"kind": "rate_limited"})[0]
    assert "ключ" in " ".join(ui.quota_message({"kind": "auth"})).lower()
    assert "ключ" in " ".join(ui.quota_message({"kind": "no_credits"})).lower()
    assert ui.wait_hint({"kind": "daily_free_limit", "reset_at_iso": iso, "approximate": False}).startswith(
        "Зачекати до"
    )
    assert ui.wait_hint({"kind": "rate_limited"}) is None


def test_history_turns_limits_to_n_pairs():
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(20)]
    h = ui.history_turns(msgs, 4)
    assert len(h) == 8 and h[0] == Turn(role="user", content="m12") and h[-1].content == "m19"
    assert ui.history_turns(msgs, 0) == []


def test_pdf_url_has_page_fragment():
    assert ui.pdf_url("data/x.pdf", 7).endswith("/data/x.pdf#page=7") and ui.pdf_url("data/x.pdf", None).endswith(
        ".pdf"
    )
