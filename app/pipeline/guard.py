"""Cheap pre-filter: empty / too long / control chars / obvious prompt-injection patterns. No LLM."""

from __future__ import annotations

import re

from app.schemas import GuardResult

MAX_CHARS = 2000

EMPTY_REPLY = "Напишіть, будь ласка, запитання щодо курсів ПОК, АКС або ОС."
TOO_LONG_REPLY = (
    f"Запитання задовге (понад {MAX_CHARS} символів). Скоротіть його, будь ласка, до однієї-двох чітких думок."
)

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-\u200F\u202A-\u202E⁠﻿]")
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+|any\s+|the\s+|your\s+)*(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)"
    r"|disregard\s+(?:all\s+|the\s+|your\s+)*(?:previous|prior|above)\s+\w+"
    r"|system\s+prompt|developer\s+message|jailbreak|you\s+are\s+now\s+(?:a|an|in)\b"
    r"|ігнору\w*\s+(?:всі\s+|усі\s+|ваші\s+|свої\s+)*(?:попередні|вищевказані)\s+(?:інструкції|правила|команди)"
    r"|забудь\w*\s+(?:всі\s+|усі\s+)?(?:інструкції|правила)"
    r"|системн\w+\s+(?:промпт|підказк|інструкці)\w*",
    re.IGNORECASE,
)


def esc(text: str) -> str:
    """Make user/slide text safe for `{{var}}` prompt rendering (it must not contain placeholders)."""
    return text.replace("{{", "{​{").replace("}}", "}​}")


def run(text: str) -> GuardResult:
    cleaned = _CTRL.sub("", text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return GuardResult(text="", ok=False, flags=["empty"], reply=EMPTY_REPLY)
    if len(cleaned) > MAX_CHARS:
        return GuardResult(text=cleaned[:MAX_CHARS], ok=False, flags=["too_long"], reply=TOO_LONG_REPLY)
    flags = ["injection"] if _INJECTION.search(cleaned) else []
    return GuardResult(text=cleaned, ok=True, flags=flags)
