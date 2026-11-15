"""Streamlit chat UI (all user-facing text in Ukrainian). Run: uv run streamlit run app/ui.py

Pure helpers (tag rendering, quota messages, reset-time formatting) live at the top and need no Streamlit session.
"""

from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

from app import llm, store
from app.config import ROOT, cfg
from app.schemas import Answer, Citation, Turn

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_TAG_RE = re.compile(r"\[(S\d+)\]")
FOOTER = (
    "Матеріали курсів © Олег Фаренюк та інші автори; ліцензія CC BY-SA, де це зазначено. "
    "Відповіді формуються автоматично суто на основі матеріалів курсів — перевіряйте їх за слайдами."
)
SPINNER_TEXT = "Шукаю в матеріалах і формую відповідь… (безкоштовні моделі повільні: кожен виклик ~20 с)"


# ---------------------------------------------------------------- pure helpers
def superscript(n: int) -> str:
    return str(n).translate(SUPERSCRIPT)


def pdf_url(pdf_path: str, page: int | None) -> str:
    """file:// link to the PDF with #page=N (browsers may block file links from a web page)."""
    url = (ROOT / pdf_path).resolve().as_uri()
    return f"{url}#page={page}" if page else url


def render_tags(text: str, citations: list[Citation], links: dict[str, str] | None = None) -> str:
    """Replace [S1] tags with superscript numbered markdown links (number = citation order).
    Tags without a citation are dropped; without a link the superscript is plain text."""
    numbers = {c.tag: i for i, c in enumerate(citations, 1) if c.tag}
    links = links or {}

    def sub(m: re.Match) -> str:
        tag = m.group(1)
        if tag not in numbers:
            return ""
        sup = superscript(numbers[tag])
        return f"[{sup}]({links[tag]})" if tag in links else sup

    return _TAG_RE.sub(sub, text)


def to_local(dt: datetime) -> datetime:
    return dt.astimezone()  # system local time zone


def format_reset(reset_iso: str | None, approximate: bool) -> str | None:
    """'03:00 (15.11)' in local time, with «приблизно» when the reset time is a guess."""
    if not reset_iso:
        return None
    local = to_local(datetime.fromisoformat(reset_iso))
    s = f"{local:%H:%M} ({local:%d.%m})"
    return f"приблизно {s}" if approximate else s


def quota_message(quota: dict) -> tuple[str, str]:
    """(headline, detail) in Ukrainian for debug['quota']."""
    kind = quota.get("kind")
    if kind == "daily_free_limit":
        when = format_reset(quota.get("reset_at_iso"), bool(quota.get("approximate")))
        detail = "Ліміт скидається щодня о 00:00 UTC."
        if when:
            detail = f"Ліміт буде скинуто {when} за вашим часом."
        return "Вичерпано денний ліміт безкоштовних запитів OpenRouter.", detail
    if kind == "rate_limited":
        return "Безкоштовні моделі зараз перевантажені — спробуйте за хвилину.", ""
    if kind == "no_credits":
        return "На ключі OpenRouter бракує коштів для цього запиту.", "Змініть API-ключ."
    if kind == "auth":
        return "API-ключ OpenRouter недійсний або не заданий.", "Вкажіть правильний ключ у бічній панелі."
    return "Помилка доступу до моделі.", ""


def wait_hint(quota: dict) -> str | None:
    when = format_reset(quota.get("reset_at_iso"), bool(quota.get("approximate")))
    return f"Зачекати до {when}" if when and quota.get("kind") == "daily_free_limit" else None


def history_turns(messages: list[dict], n_turns: int) -> list[Turn]:
    """Last n_turns user+assistant pairs as Turn objects."""
    recent = messages[-2 * n_turns :] if n_turns > 0 else []
    return [Turn(role=m["role"], content=m["content"]) for m in recent]


def source_links(answer: Answer) -> dict[str, str]:
    docs = store.documents()
    out = {}
    for c in answer.citations:
        doc = docs.get(c.doc_id)
        if c.tag and doc:
            out[c.tag] = pdf_url(doc.pdf_path, c.page_start)
    return out


# ---------------------------------------------------------------- Streamlit parts
@st.cache_data(ttl=300, show_spinner=False)
def _key_status(nonce: int) -> dict:  # nonce busts the cache when the key is changed
    return llm.key_status()


def _thumb(pdf_path: str, page: int) -> bytes | None:
    from app.ingest.figures import page_png

    try:
        return page_png(pdf_path, page, dpi=70)
    except Exception:  # noqa: BLE001 — a missing PDF must not break the answer
        return None


def _render_sources(answer: Answer) -> None:
    if not answer.citations:
        return
    docs = store.documents()
    title = "Найближчі слайди" if answer.abstained else "Джерела"
    with st.expander(f"{title} ({len(answer.citations)})"):
        for i, c in enumerate(answer.citations, 1):
            doc = docs.get(c.doc_id)
            st.markdown(f"**{superscript(i)} {c.label}**" + (f" — {c.title}" if c.title else ""))
            cols = st.columns([1, 2])
            if doc and c.page_start:
                png = _thumb(doc.pdf_path, c.page_start)
                if png:
                    cols[0].image(png)
            links = [f"[{u}]({u})" for u in c.urls]
            if doc:
                links.append(f"[відкрити PDF]({pdf_url(doc.pdf_path, c.page_start)})")
            cols[1].markdown("  \n".join(links) if links else "—")


def _render_debug(answer: Answer) -> None:
    d = answer.debug
    with st.expander("Налагодження"):
        st.write(f"trace_id: `{answer.trace_id}`")
        r = d.get("route")
        if r:
            st.write(f"Маршрут: **{r.get('route')}**, впевненість {r.get('confidence')}, причина: {r.get('reason')}")
        st.write("Запити:", d.get("queries") or (r or {}).get("queries"))
        titles = {
            cid: (c.title or "")
            for cid, c in store.chunks().items()
            if cid in {h["chunk_id"] for h in d.get("hits", [])}
        }
        st.write("Топ-результати (rerank):")
        st.table(
            [
                {"chunk_id": h["chunk_id"], "назва": titles.get(h["chunk_id"], ""), "score": h["score"]}
                for h in d.get("hits", [])
            ]
        )
        st.write("Gate:", d.get("gate"))
        st.write("Верифікація:", d.get("verify") or ("вимкнено" if d.get("verify_skipped") else None))
        st.write("Час по етапах (с):", d.get("timings"))
        st.write("Моделі за викликами:", d.get("llm_calls"))
        if d.get("error"):
            st.write("Помилка:", d["error"])


def _render_quota_banner(quota: dict) -> None:
    headline, detail = quota_message(quota)
    (st.warning if quota.get("kind") == "rate_limited" else st.error)(f"**{headline}** {detail}".strip())
    hint = wait_hint(quota)
    c1, c2 = st.columns(2)
    c1.markdown("**Змінити API-ключ** — поле «OpenRouter API-ключ» у бічній панелі (діє лише в цьому сеансі).")
    c2.markdown(f"**{hint}**" if hint else "**Зачекати хвилину** і повторити запитання.")
    if st.button("Повторити останнє запитання"):
        st.session_state.retry = True


def _render_answer(answer: Answer, debug_on: bool) -> None:
    st.markdown(render_tags(answer.text, answer.citations, source_links(answer)))
    _render_sources(answer)
    if debug_on:
        _render_debug(answer)


def _sidebar() -> bool:
    c = cfg()
    st.sidebar.title("Налаштування")
    debug_on = st.sidebar.toggle("Режим налагодження")
    st.session_state.verify = st.sidebar.checkbox(
        "Перевіряти цитування (повільніше)", value=bool((c.get("pipeline") or {}).get("verify", False))
    )
    key = st.sidebar.text_input("OpenRouter API-ключ", type="password", help="Лише для цього сеансу.")
    st.sidebar.caption("Ключ зберігається тільки в пам'яті цього сеансу — не записується на диск і в логи.")
    if key != st.session_state.get("key", ""):
        st.session_state.key = key
        st.session_state.key_nonce = st.session_state.get("key_nonce", 0) + 1
        llm.set_api_key(key or None)
    status = _key_status(st.session_state.get("key_nonce", 0))
    if "error" in status:
        st.sidebar.warning(f"Стан ключа: не вдалося перевірити ({status['error']})")
    else:
        limit = status.get("limit")
        st.sidebar.markdown(
            f"**Ключ:** {status.get('label') or '—'}  \n"
            f"Безкоштовний тариф: {'так' if status.get('is_free_tier') else 'ні'}  \n"
            f"Використано: {status.get('usage')} / ліміт: {limit if limit is not None else '—'}"
        )
    st.sidebar.markdown("**Моделі:**")
    for role in ("fast", "generator"):
        st.sidebar.caption(f"{role}: `{llm.model_for(role)[0]}`")
    st.sidebar.caption("Резервні: " + ", ".join(f"`{m}`" for m in c["llm"].get("fallbacks", {}).get("generator", [])))
    st.sidebar.caption("Безкоштовні моделі: ~50 запитів на день на акаунт, ліміт скидається о 00:00 UTC.")
    return debug_on


def main() -> None:
    from app.pipeline import answer as pipeline

    st.set_page_config(page_title="Асистент курсів ПОК · АКС · ОС", page_icon="🎓")
    st.title("Асистент курсів ПОК · АКС · ОС")
    st.caption("Відповідає лише за матеріалами курсів, із посиланнями на слайди.")
    debug_on = _sidebar()
    msgs: list[dict] = st.session_state.setdefault("messages", [])

    question = None
    if st.session_state.pop("retry", False) and st.session_state.get("last_q"):
        while msgs and msgs[-1].get("answer") and msgs[-1]["answer"].debug.get("error_kind"):
            msgs.pop()  # failed attempt's notice
            if msgs and msgs[-1]["role"] == "user":
                msgs.pop()
        question = st.session_state.last_q

    for m in msgs:
        with st.chat_message(m["role"]):
            if m.get("answer"):
                _render_answer(m["answer"], debug_on)
            else:
                st.markdown(m["content"])

    question = st.chat_input("Поставте запитання про ПОК, АКС або ОС") or question
    if question:
        st.session_state.last_q = question
        hist = history_turns(msgs, cfg()["chat"]["history_turns"])
        msgs.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        cfg().setdefault("pipeline", {})["verify"] = bool(st.session_state.get("verify"))
        with st.chat_message("assistant"):
            with st.spinner(SPINNER_TEXT):
                ans = pipeline.run(question, hist)
            _render_answer(ans, debug_on)
        msgs.append({"role": "assistant", "content": ans.text, "answer": ans})
        quota = ans.debug.get("quota") if ans.debug.get("error_kind") == "quota" else None
        st.session_state.quota = quota  # banner stays until the next successful answer

    if st.session_state.get("quota"):
        _render_quota_banner(st.session_state.quota)

    st.divider()
    st.caption(FOOTER)


if __name__ == "__main__":
    main()
