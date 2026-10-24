"""An LLM extractor (Claude, tool use) that reads what the rules cannot, and is held to the same
standard: every value must quote the words it rests on, and the quote must be in the message.

Used as `HybridExtractor`: the rule extractor runs first; the model is asked only for the fields
the rules did not find, so a model outage or a hallucination cannot remove or overwrite what the
rules read. Values are validated against the same vocabularies (occupation ids, licence classes,
CEFR levels, dates not in the past). The model never sees the candidate's name or number.

All numbers in this repository's reports come from the rule extractor alone: no API key was
available where they were produced. `tests/test_llm_extractor.py` checks the validation with a
stub client.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from .. import config
from .rules import CEFR, Fact, Reading, RuleExtractor

log = logging.getLogger(__name__)
LICENCES = ["B", "BE", "C1", "C1E", "C", "CE", "D1", "D", "DE", "code95", "forklift", "adr", "tachograph_card"]
TOOL = {
    "name": "record_facts",
    "description": "Record facts the candidate states about their work situation. Only what the message says; every fact quotes the exact words.",
    "input_schema": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": ["occupation", "qualification", "recognition", "licences", "commute_km", "shifts",
                                                             "start_date", "german_level", "experience_years", "employment"]},
                        "value": {},
                        "quote": {"type": "string", "description": "the exact words of the message this rests on"},
                    },
                    "required": ["field", "value", "quote"],
                },
            }
        },
        "required": ["facts"],
    },
}
SYSTEM = (
    "You read one WhatsApp message from a job candidate in Germany and record facts with the record_facts tool. "
    "Never record age, nationality, religion, family, health or anything about other people. "
    "Values: occupation = list of ids from {occupations}; qualification = domestic|foreign|none; "
    "recognition = recognised|in_progress|not_started; licences = list from {licences}; shifts = object with early/late/night/weekend booleans; "
    "start_date = ISO date (today is {today}); german_level = none|A1|A2|B1|B2|C1|C2; experience_years = integer; "
    "employment = list of full_time|part_time; commute_km = integer. The question the candidate is answering: {asked}."
)


class ClaudeExtractor:
    name = "claude"

    def __init__(self, client: Any = None, model: str | None = None) -> None:
        if client is None:
            import anthropic  # optional dependency: pip install ".[llm]"

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or os.environ.get("FKP_LLM_MODEL", "claude-sonnet-4-5")

    def facts(self, text: str, today: date, asked: str | None, skip: set[str]) -> list[Fact]:
        system = SYSTEM.format(occupations=", ".join(config.occupations()), licences=", ".join(LICENCES), today=today.isoformat(),
                               asked=asked or "none (first message)")
        msg = self.client.messages.create(model=self.model, max_tokens=800, system=system, tools=[TOOL],
                                          tool_choice={"type": "tool", "name": "record_facts"},
                                          messages=[{"role": "user", "content": text}])
        block = next((b for b in msg.content if getattr(b, "type", "") == "tool_use"), None)
        raw = (getattr(block, "input", None) or {}).get("facts", []) if block else []
        out = []
        for f in raw if isinstance(raw, list) else []:
            fact = validate(f, text, today)
            if fact and fact.field not in skip:
                out.append(fact)
        return out


def validate(f: dict[str, Any], text: str, today: date) -> Fact | None:
    """A model fact, or None if it quotes words the message does not contain or has a value outside
    the vocabulary."""
    field, value, quote = f.get("field"), f.get("value"), str(f.get("quote", "")).strip()
    if not quote:
        return None
    i = text.lower().find(quote.lower())
    if i < 0:
        return None
    occ = set(config.occupations())
    ok = False
    if field == "occupation":
        value = [value] if isinstance(value, str) else value
        ok = isinstance(value, list) and bool(value) and all(v in occ for v in value)
    elif field == "qualification":
        ok = value in ("domestic", "foreign", "none")
    elif field == "recognition":
        ok = value in ("recognised", "in_progress", "not_started")
    elif field == "licences":
        ok = isinstance(value, list) and all(v in LICENCES for v in value)
    elif field == "shifts":
        ok = isinstance(value, dict) and bool(value) and all(k in ("early", "late", "night", "weekend") and isinstance(v, bool) for k, v in value.items())
    elif field == "start_date":
        try:
            ok = date.fromisoformat(str(value)) >= today
        except ValueError:
            ok = False
    elif field == "german_level":
        ok = value in ("none", *CEFR)
    elif field in ("experience_years", "commute_km"):
        ok = isinstance(value, int) and 0 <= value <= (50 if field == "experience_years" else 300)
    elif field == "employment":
        value = [value] if isinstance(value, str) else value
        ok = isinstance(value, list) and bool(value) and all(v in ("full_time", "part_time") for v in value)
    if not ok:
        return None
    return Fact(str(field), value, i, i + len(quote), 0.7)


class HybridExtractor:
    """Rules first; the model only fills fields the rules left empty."""

    name = "rules+claude"

    def __init__(self, llm: ClaudeExtractor, rules: RuleExtractor | None = None) -> None:
        self.rules = rules or RuleExtractor()
        self.llm = llm

    def read(self, text: str, lang: str, today: date, asked: str | None = None, expect: frozenset[str] = frozenset()) -> Reading:
        r = self.rules.read(text, lang, today, asked, expect)
        if r.intents & {"opt_out", "human"} or not text.strip():
            return r
        have = {f.field for f in r.facts} | {"location", "email", "full_name"}
        try:
            r.facts += self.llm.facts(text, today, asked, have)
        except Exception as e:  # noqa: BLE001 - the model is an extra, never a dependency
            log.warning("llm extractor failed, rules only: %s", str(e)[:200])
        return r
