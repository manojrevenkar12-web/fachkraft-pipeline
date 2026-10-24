"""Data protection helpers.

* Health information is special-category data (GDPR Art. 9). Candidates mention it unprompted
  ("seit der OP kann ich nicht mehr heben"). Sentences that mention health are removed from stored
  messages and never reach a profile, a summary or the ATS.
* Opt-outs are kept only as a salted hash of the number.
"""

from __future__ import annotations

import hashlib
import os
import re

from . import config
from .text import find_terms, fold

REMOVED = "[health information removed]"
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*\n?|\n")


def _health_terms() -> list[str]:
    return list(config.lexicon()["health_terms"]["any"])


def mentions_health(text: str, lang: str | None = None) -> bool:
    folded = fold(text)
    if find_terms(folded, _health_terms(), lang or "ru"):
        return True
    # Cyrillic entries are stems ("інвалід" -> "інвалідність", "беремен" -> "беременна")
    stems = [fold(t) for t in _health_terms() if any("\u0400" <= c <= "\u04ff" for c in t)]
    return any(re.search(r"(?<!\w)" + re.escape(st), folded) for st in stems)


def redact(text: str, lang: str | None = None) -> tuple[str, bool]:
    """The text with every sentence that mentions health replaced, and whether anything was."""
    out, hit = [], False
    for m in _SENTENCE.finditer(text):
        s = m.group(0)
        if s.strip() and mentions_health(s, lang):
            lead = s[: len(s) - len(s.lstrip())]
            out.append(lead + REMOVED + ("\n" if s.endswith("\n") else ""))
            hit = True
        else:
            out.append(s)
    return ("".join(out).strip() if hit else text), hit


def phone_hash(phone: str) -> str:
    salt = os.environ.get("FKP_HASH_SALT", "dev-salt-change-me")
    digits = re.sub(r"\D", "", phone)
    return hashlib.sha256(f"{salt}:{digits}".encode()).hexdigest()
