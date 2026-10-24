"""Jobs: what a role requires, and the anti-discrimination check (AGG) every job text passes.

A job's hard requirements filter; soft ones score. A German level is a hard requirement only with a
stated reason, because requiring language skills the work does not need is indirect
discrimination by origin under the AGG (LAG Hessen, 16 Sa 1619/14: "Deutsch als Muttersprache").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

import yaml

from . import config, geo
from .text import find_terms, fold

SHIFTS = ("early", "late", "night", "weekend")
LICENCES = ("B", "BE", "C1", "C1E", "C", "CE", "D1", "D", "DE", "code95", "forklift", "adr", "tachograph_card")
CEFR_RANK = {"none": 0, "A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


@dataclass
class Job:
    id: str
    title: str
    occupation: str
    plz: str
    radius_km: int
    shifts: list[str]
    employment: list[str]
    start_by: date
    must: dict[str, Any] = field(default_factory=dict)
    german_level: dict[str, str] | None = None
    soft: dict[str, Any] = field(default_factory=dict)
    pay: str = ""
    text: str = ""
    open: bool = True

    @property
    def place(self) -> geo.Place:
        p = geo.by_plz(self.plz)
        if p is None:
            raise ValueError(f"{self.id}: unknown postcode {self.plz}")
        return p

    @property
    def german_min(self) -> str | None:
        """The level that filters, or None when the job gives no reason for it."""
        g = self.german_level or {}
        if g.get("min") and str(g.get("justification", "")).strip():
            return str(g["min"])
        return None

    @property
    def regulated(self) -> bool:
        return bool(config.occupations()[self.occupation].get("regulated"))

    @property
    def needs_recognition(self) -> bool:
        return bool(self.must.get("recognition")) or self.regulated

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "occupation": self.occupation,
            "plz": self.plz,
            "place": self.place.name,
            "radius_km": self.radius_km,
            "shifts": self.shifts,
            "employment": self.employment,
            "start_by": self.start_by.isoformat(),
            "must": self.must,
            "german_level": self.german_level,
            "soft": self.soft,
            "pay": self.pay,
            "text": self.text,
            "open": self.open,
        }


def parse(d: dict[str, Any]) -> Job:
    occ = config.occupations()
    if d.get("occupation") not in occ:
        raise ValueError(f"{d.get('id')}: unknown occupation {d.get('occupation')!r}")
    for s in d.get("shifts", []):
        if s not in SHIFTS:
            raise ValueError(f"{d['id']}: unknown shift {s!r}")
    for lic in (d.get("must") or {}).get("licences", []):
        if lic not in LICENCES:
            raise ValueError(f"{d['id']}: unknown licence {lic!r}")
    g = d.get("german_level")
    if g and g.get("min") not in CEFR_RANK:
        raise ValueError(f"{d['id']}: German level must be one of {list(CEFR_RANK)}")
    sb = d.get("start_by")
    job = Job(
        id=str(d["id"]),
        title=str(d["title"]),
        occupation=d["occupation"],
        plz=str(d["plz"]),
        radius_km=int(d.get("radius_km", 30)),
        shifts=list(d.get("shifts", [])),
        employment=list(d.get("employment", ["full_time"])),
        start_by=sb if isinstance(sb, date) else date.fromisoformat(str(sb)),
        must=dict(d.get("must") or {}),
        german_level=dict(g) if g else None,
        soft=dict(d.get("soft") or {}),
        pay=str(d.get("pay", "")),
        text=str(d.get("text", "")),
        open=bool(d.get("open", True)),
    )
    _ = job.place
    return job


def load(path: str | None = None) -> list[Job]:
    p = path or config.CONFIG_DIR / "jobs.example.yaml"
    return [parse(d) for d in yaml.safe_load(open(p, encoding="utf-8"))]


# -- AGG check -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class AggIssue:
    rule: str
    severity: str  # block, warn
    quote: str
    advice: str


_GENDER_MARK = re.compile(
    r"\((?:m|w|d|f|x|div|gn|all genders)[/|,\s]*(?:m|w|d|f|x|div)?[/|,\s]*(?:m|w|d|f|x|div)?\)|\*in\b|:in\b|_in\b|/-?in\b|all genders|alle geschlechter",
    re.I,
)
_MALE = re.compile(r"\b(?:mann|männer|herrn?|herren|kerl|kerle|jungs|man|men|guys?|gentlem[ae]n)\b")
_FEMALE = re.compile(r"\b(?:frau|frauen|dame|damen|mädels|woman|women|lady|ladies)\b|\w{3,}in\b")


@dataclass(frozen=True)
class _Rule:
    id: str
    severity: str
    advice: str
    patterns: tuple[re.Pattern[str], ...]
    nomark: tuple[re.Pattern[str], ...]  # only when the ad has no all-gender form anywhere


@lru_cache(maxsize=1)
def agg_rules() -> tuple[tuple[_Rule, ...], tuple[str, ...]]:
    spec = config.load("agg")
    rules = []
    for r in spec["rules"]:
        plain = [p for p in r["patterns"] if not p.startswith("!nomark ")]
        nomark = [p.removeprefix("!nomark ") for p in r["patterns"] if p.startswith("!nomark ")]
        rules.append(
            _Rule(r["id"], r["severity"], r["advice"], tuple(re.compile(p, re.I) for p in plain), tuple(re.compile(p, re.I) for p in nomark))
        )
    return tuple(rules), tuple(fold(x) for x in spec["inclusive"])


def block_rules() -> set[str]:
    return {r.id for r in agg_rules()[0] if r.severity == "block"}


def _sentence(text: str, s: int, e: int) -> str:
    a = max(text.rfind(c, 0, s) for c in ".!?\n")
    b = min([i for i in (text.find(c, e) for c in ".!?\n") if i >= 0] or [len(text)])
    return text[a + 1 : b]


def check_agg(job: Job | dict[str, Any]) -> list[AggIssue]:
    """Problems in a job's title and text, and requirements without a reason."""
    if isinstance(job, Job):
        title, text, german = job.title, job.text, job.german_level
    else:
        title, text, german = str(job.get("title", "")), str(job.get("text", "")), job.get("german_level")
    whole = f"{title}\n{text}"
    low = whole.lower()
    folded = fold(whole)
    marked = bool(_GENDER_MARK.search(whole))
    rules, inclusive = agg_rules()
    describes_team = re.compile(config.load("agg")["describes_team"], re.I)
    out: list[AggIssue] = []
    for rule in rules:
        for pat in rule.patterns + (() if marked else rule.nomark):
            hit = None
            for m in pat.finditer(low):
                # "Wir freuen uns über Bewerbungen unabhängig von Herkunft, Religion und Alter" and
                # "wir fragen nicht nach dem Familienstand" are the opposite of a requirement
                if find_terms(folded[max(0, m.start() - 80) : m.start()], list(inclusive)):
                    continue
                if rule.id == "age" and re.search(r"\d", m.group(0)) and describes_team.search(_sentence(low, m.start(), m.end())):
                    continue
                if rule.id == "gender-only":
                    sent = _sentence(low, m.start(), m.end())
                    if _MALE.search(sent) and _FEMALE.search(sent):
                        continue  # "Frauen und Männer": both addressed
                hit = m
                break
            if hit:
                quote = (whole if len(whole) == len(low) else low)[hit.start() : hit.end()]
                out.append(AggIssue(rule.id, rule.severity, quote, rule.advice))
                break
    if not _GENDER_MARK.search(title):
        out.append(AggIssue("gender-title", "warn", title, config.load("agg")["gender_title_advice"]))
    if german and german.get("min") and not str(german.get("justification", "")).strip():
        out.append(AggIssue("german-without-reason", "warn", f"Deutsch {german.get('min')}", config.load("agg")["german_reason_advice"]))
    return out
