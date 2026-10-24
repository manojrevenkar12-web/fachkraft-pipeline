"""Text normalisation that keeps character positions, so evidence spans point into the original
message.

`fold` maps every character to exactly one character: lower case, no diacritics, Cyrillic look-alike
letters in licence classes handled separately. Matching runs on the folded text and the folded
patterns; a match at [i, j) in the folded text is the same characters [i, j) of the original.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_ARABIC = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"}
_SPECIAL = {
    **_ARABIC,
    "ß": "s",
    "ı": "i",
    "İ": "i",
    "ł": "l",
    "Ł": "l",
    "ø": "o",
    "æ": "a",
    "œ": "o",
    "đ": "d",
    "ð": "d",
    "’": "'",
    "`": "'",
    "´": "'",
}
# Ukrainian/Russian letters keep their identity: only Latin diacritics are removed.


def _fold_char(c: str) -> str:
    if c in _SPECIAL:
        return _SPECIAL[c]
    low = c.lower()
    if len(low) != 1:
        low = low[0]
    if "Ѐ" <= low <= "ӿ" or "؀" <= low <= "ۿ":
        if low == "ё":
            return "е"
        return low
    decomposed = unicodedata.normalize("NFKD", low)
    base = decomposed[0] if decomposed else low
    return base if len(base) == 1 else low


def fold(text: str) -> str:
    out = "".join(_fold_char(c) for c in text)
    assert len(out) == len(text)
    return out


# Arabic letters are \w as well, so (?<!\w) bounds work across scripts.
_LEFT = r"(?<![\w])"
_RIGHT = r"(?![\w])"
INFLECTING = {"tr", "pl", "ro", "uk", "ru"}


@lru_cache(maxsize=8192)
def term_regex(term: str, suffix: int = 0) -> re.Pattern[str]:
    """A word-bounded pattern for a folded term. `suffix` allows that many extra letters at the end,
    for languages that inflect nouns (Polish "w Berlinie", Russian "работаю сварщиком",
    Turkish "Berlin'de")."""
    t = fold(term.strip())
    parts = [re.escape(p) for p in re.split(r"\s+", t) if p]
    body = r"\s+".join(parts).replace(r"\-", r"[-\s]?")
    tail = rf"(?:'?\w{{0,{suffix}}})" if suffix else ""
    # Arabic glues "and", "with", "for" and the article to the word: ومسائية = "and evening"
    head = "(?:[\u0648\u0641\u0628\u0644]?\u0627\u0644|[\u0648\u0641\u0628\u0644])?" if t and "\u0600" <= t[0] <= "\u06ff" else ""
    return re.compile(_LEFT + head + "(" + body + ")" + tail + _RIGHT)


def find_terms(folded: str, terms: list[str], lang: str | None = None) -> list[tuple[int, int, str]]:
    """Every (start, end, term) occurrence, longest term first, without overlaps."""
    hits: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for term in sorted(set(terms), key=len, reverse=True):
        allow = 4 if lang in INFLECTING and len(term) >= 5 else 0
        for m in term_regex(term, allow).finditer(folded):
            s, e = m.start(), m.end()
            if any(s < te and ts < e for ts, te in taken):
                continue
            taken.append((s, e))
            hits.append((s, e, term))
    return sorted(hits)


def contains_any(folded: str, terms: list[str], lang: str | None = None) -> bool:
    return bool(find_terms(folded, terms, lang))


def window(text: str, start: int, end: int, before: int, after: int) -> str:
    return text[max(0, start - before) : min(len(text), end + after)]
