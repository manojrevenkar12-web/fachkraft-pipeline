"""The offline extractor: facts from a candidate's free-text message, each with the words it rests on.

It reads eight languages with the vocabularies in config/lexicon.yaml and config/occupations.yaml.
Every value comes with the span of the message it was read from, so a recruiter can see why the
profile says what it says, and a value without evidence never enters a profile.

What it deliberately never extracts: age, nationality, religion, family status and health. Age
statements ("ich bin 35 Jahre alt") are recognised only so they are *not* read as experience.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .. import config, geo
from ..text import contains_any, find_terms, fold

FIELDS = (
    "occupation",
    "qualification",
    "recognition",
    "licences",
    "location",
    "commute_km",
    "shifts",
    "start_date",
    "german_level",
    "experience_years",
    "employment",
    "email",
    "full_name",
)
CEFR = ("A1", "A2", "B1", "B2", "C1", "C2")
LEVEL_WORDS = {"none": "none", "basic": "A2", "good": "B2", "fluent": "C1"}
_CLASS = re.compile(r"(?<![\w+])(C1E|C1\+E|CE|C\+E|C1|C|BE|B\+E|B|D1E|D1|DE|D\+E|D|T|L)(?![\w+])")
_CYR_TO_LAT = str.maketrans({"С": "C", "Е": "E", "В": "B", "Д": "D", "с": "c", "е": "e", "в": "b"})
_IMPLIED = {"CE": {"C", "B"}, "C": {"B"}, "C1E": {"C1", "B"}, "C1": {"B"}, "BE": {"B"}, "D": {"B"}, "D1": {"B"}, "DE": {"D", "B"}, "D1E": {"D1", "B"}}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATE_NUM = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?(?!\d)")
_DATE_ISO = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
_NUMBER = re.compile(r"(?<![\d.,])(\d{1,3})(?:[.,]\d+)?(?![\d])")
_YEAR = re.compile(r"(?<!\d)(19[6-9]\d|20[0-3]\d)(?!\d)")
_AGE_WORDS = ["alt", "jahre alt", "years old", "year old", "yaşında", "yasinda", "lat mam", "ani am", "років мені", "мені", "мне", "лет мне", "عمري"]
_SINCE = ["seit", "since", "od", "din", "з", "с", "منذ", "beri", "dir"]
_QUAL_NONE = [
    "ungelernt",
    "quereinsteiger",
    "quereinsteigerin",
    "ohne ausbildung",
    "keine ausbildung",
    "no qualification",
    "no formal training",
    "unskilled",
    "without training",
    "eğitimim yok",
    "egitimim yok",
    "kalifiye değilim",
    "bez wykształcenia",
    "bez wyksztalcenia",
    "bez kwalifikacji",
    "fără calificare",
    "fara calificare",
    "без освіти",
    "без образования",
    "без кваліфікації",
    "بدون شهادة",
    "بدون تأهيل",
]
_QUAL_YES = [
    "ausbildung",
    "gelernt",
    "gelernter",
    "gelernte",
    "examen",
    "examiniert",
    "examinierte",
    "abschluss",
    "geselle",
    "gesellenbrief",
    "meister",
    "studium",
    "diplom",
    "apprenticeship",
    "qualified",
    "trained",
    "diploma",
    "degree",
    "certificate",
    "eğitim",
    "diploma",
    "meslek lisesi",
    "wykształcenie",
    "dyplom",
    "szkoła zawodowa",
    "calificare",
    "diplomă",
    "școală profesională",
    "освіта",
    "диплом",
    "образование",
    "училище",
    "технікум",
    "техникум",
    "شهادة",
    "دبلوم",
    "تأهيل",
]


class _Asked:
    """Compares equal to the current question and to every earlier unanswered one."""

    def __init__(self, current: str | None, expect: frozenset[str]) -> None:
        self.fields = {current, *expect} - {None}

    def __eq__(self, other: object) -> bool:
        return other in self.fields

    def __hash__(self) -> int:
        return hash(frozenset(self.fields))


@dataclass
class Fact:
    field: str
    value: Any
    start: int
    end: int
    confidence: float = 0.9

    def evidence(self, text: str) -> str:
        return text[self.start : self.end]


@dataclass
class Reading:
    facts: list[Fact] = field(default_factory=list)
    intents: set[str] = field(default_factory=set)  # yes, no, opt_out, human
    age_mentioned: bool = False
    health_mentioned: bool = False

    def get(self, name: str) -> Fact | None:
        return next((f for f in self.facts if f.field == name), None)


def _terms(section: dict[str, Any], lang: str, mix: bool = True) -> list[str]:
    """The words for `lang`, plus the language-independent ones. With `mix`, German and English
    words too: people in Germany mix them in ("Staplerschein", "Code 95") whatever they write in.
    Intent words (yes, no, negation) never mix: Polish "no" means "well", not "no"."""
    out = list(section.get(lang, [])) + list(section.get("any", []))
    if mix:
        for other in ("de", "en"):
            if other != lang:
                out += section.get(other, [])
    return out


def _near(folded: str, start: int, end: int, terms: list[str], lang: str, before: int = 30, after: int = 30) -> bool:
    return contains_any(folded[max(0, start - before) : end + after], terms, lang)


def _gap(folded: str, start: int, end: int, terms: list[str], lang: str) -> int:
    """Characters between a span and the closest of the terms (a large number if none)."""
    best = 10_000
    for s, e, _ in find_terms(folded, terms, lang):
        best = min(best, start - e if e <= start else s - end if s >= end else 0)
    return best


class RuleExtractor:
    name = "rules"

    def __init__(self) -> None:
        self.lex = config.lexicon()
        self.occ = config.occupations()

    # -- public --------------------------------------------------------------------------------

    def read(self, text: str, lang: str, today: date, asked: str | None = None, expect: frozenset[str] = frozenset()) -> Reading:
        """`asked` is the question just put; `expect` are earlier questions still unanswered. Both
        let short answers ("8", "früh und spät", "B") count that would be too ambiguous in an
        unprompted message."""
        folded = fold(text)
        r = Reading()
        r.intents = self._intents(folded, lang)
        r.health_mentioned = contains_any(folded, self.lex["health_terms"]["any"], lang)
        r.age_mentioned = self._age(folded, lang)
        asked_ctx = _Asked(asked, expect)
        for fn in (
            self._occupation,
            self._qualification,
            self._recognition,
            self._licences,
            self._location,
            self._commute,
            self._shifts,
            self._start,
            self._german,
            self._experience,
            self._employment,
            self._email,
        ):
            fn(text, folded, lang, today, asked_ctx, r)
        if asked == "full_name":
            self._full_name(text, r)
        return r

    # -- intents -------------------------------------------------------------------------------

    def _intents(self, folded: str, lang: str) -> set[str]:
        out = set()
        stripped = folded.strip(" .!?\n")
        # "stop" in any language counts in a short message: people switch to their own language to say it
        everywhere = [t for k, v in self.lex["opt_out"].items() for t in v] if len(stripped.split()) <= 5 else _terms(self.lex["opt_out"], lang)
        if contains_any(folded, everywhere, lang):
            out.add("opt_out")
        if contains_any(folded, _terms(self.lex["human"], lang), lang):
            out.add("human")
        # yes/no only as (nearly) the whole answer: "ja", "ja, passt", "nein danke"
        words = stripped.split()
        if 0 < len(words) <= 4:
            if contains_any(stripped, _terms(self.lex["yes"], lang, mix=False), lang):
                out.add("yes")
            if contains_any(stripped, _terms(self.lex["no"], lang, mix=False), lang):
                out.add("no")
        return out

    def _age(self, folded: str, lang: str) -> bool:
        return any(15 <= int(m.group(1)) <= 70 and _near(folded, m.start(), m.end(), _AGE_WORDS, lang, 12, 18) for m in _NUMBER.finditer(folded))

    # -- fields --------------------------------------------------------------------------------

    def _occupation(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        alias_to_id: dict[str, str] = {}
        for oid, spec in self.occ.items():
            for key, aliases in spec["aliases"].items():
                if key in ("any", lang, "en"):
                    for a in aliases:
                        alias_to_id.setdefault(fold(a), oid)
        seen: list[str] = []
        first: tuple[int, int] | None = None
        for s, e, term in find_terms(folded, list(alias_to_id), lang):
            oid = alias_to_id[term]
            # "chef" means boss in German; only read it as a cook in an English message
            if term == "chef" and lang != "en":
                continue
            if oid not in seen:
                seen.append(oid)
                first = first or (s, e)
        if seen and first:
            r.facts.append(Fact("occupation", seen, first[0], first[1]))

    def _qualification(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        none = find_terms(folded, _QUAL_NONE, lang)
        if none:
            s, e, _ = none[0]
            r.facts.append(Fact("qualification", "none", s, e))
            return
        foreign = find_terms(folded, _terms(self.lex["foreign_training"], lang), lang)
        domestic = find_terms(folded, _terms(self.lex["domestic_training"], lang), lang)
        if domestic:
            s, e, _ = domestic[0]
            r.facts.append(Fact("qualification", "domestic", s, e))
        elif foreign:
            s, e, _ = foreign[0]
            r.facts.append(Fact("qualification", "foreign", s, e, 0.8))
        elif find_terms(folded, [t for st in self.lex["recognition"].values() for t in _terms(st, lang)], lang):
            # talking about recognition (Anerkennung) means the qualification is from abroad
            s, e, _ = find_terms(folded, [t for st in self.lex["recognition"].values() for t in _terms(st, lang)], lang)[0]
            r.facts.append(Fact("qualification", "foreign", s, e, 0.75))
        elif asked == "qualification":
            yes = find_terms(folded, _QUAL_YES, lang)
            if "no" in r.intents:
                r.facts.append(Fact("qualification", "none", 0, len(text), 0.7))
            elif yes:
                s, e, _ = yes[0]
                r.facts.append(Fact("qualification", "trained", s, e, 0.6))

    def _recognition(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        rec = self.lex["recognition"]
        # most specific first: "nicht anerkannt" contains "anerkannt"
        for status in ("not_started", "in_progress", "recognised"):
            hits = find_terms(folded, _terms(rec[status], lang), lang)
            if hits:
                s, e, _ = hits[0]
                r.facts.append(Fact("recognition", status, s, e))
                return
        if asked == "recognition":
            if "yes" in r.intents:
                r.facts.append(Fact("recognition", "recognised", 0, len(text), 0.7))
            elif "no" in r.intents:
                r.facts.append(Fact("recognition", "not_started", 0, len(text), 0.7))

    def _licences(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        found: dict[str, tuple[int, int]] = {}
        for key in ("code95", "forklift", "adr", "tachograph_card"):
            hits = find_terms(folded, _terms(self.lex[key], lang), lang)
            if hits:
                found.setdefault(key, hits[0][:2])
        # a class letter counts next to a licence word, another licence item ("CE and code 95") or
        # a driving job ("truck driver with CE")
        driver_terms = [a for oid in ("berufskraftfahrer", "busfahrer") for v in self.occ[oid]["aliases"].values() for a in v]
        context = _terms(self.lex["licence_context"], lang) + _terms(self.lex["code95"], lang) + _terms(self.lex["adr"], lang) + driver_terms
        german = _terms(self.lex["german_context"], lang)
        latin = text.translate(_CYR_TO_LAT)
        for m in _CLASS.finditer(latin):
            cls = m.group(1).replace("+", "")
            s, e = m.start(1), m.end(1)
            near_licence = _near(folded, s, e, context, lang, 35, 25)
            near_german = _near(folded, s, e, german, lang, 25, 25)
            # C1 is a lorry class and a CEFR level: it belongs to whichever word is closer
            if cls == "C1" and near_german and (not near_licence or _gap(folded, s, e, german, lang) < _gap(folded, s, e, context, lang)):
                continue
            if cls in ("T", "L") and not near_licence:
                continue
            if near_licence or (asked == "licences" and not near_german):
                found.setdefault(cls, (s, e))
        if not found:
            if asked == "licences" and "no" in r.intents:
                r.facts.append(Fact("licences", [], 0, len(text), 0.7))
            return
        classes = set(found)
        for c in list(classes):
            classes |= _IMPLIED.get(c, set())
        first = min(found.values())
        last = max(v[1] for v in found.values())
        r.facts.append(Fact("licences", sorted(classes), first[0], last))

    def _location(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        hit = geo.find(text, lang)
        if hit:
            place, s, e = hit
            r.facts.append(Fact("location", {"place": place.name, "plz": place.plz, "lat": place.lat, "lon": place.lon}, s, e))

    def _commute(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        units = _terms(self.lex["commute_context"], lang)
        minutes = [fold(w) for w in self.lex["minute_words"]]
        for m in _NUMBER.finditer(folded):
            n = int(m.group(1))
            tail = folded[m.end() : m.end() + 14]
            unit_hit = find_terms(tail, units, lang)
            if not unit_hit or unit_hit[0][0] > 2:
                continue
            is_min = fold(unit_hit[0][2]) in minutes
            # "30 Minuten" is about 25 km at typical commuting speed; the original is kept as evidence
            value = round(n * 0.8) if is_min else n
            if 1 <= value <= 300:
                r.facts.append(Fact("commute_km", value, m.start(), m.end() + unit_hit[0][1]))
                return
        if asked == "commute":
            m2 = _NUMBER.search(folded)
            if m2 and 1 <= int(m2.group(1)) <= 150:
                r.facts.append(Fact("commute_km", int(m2.group(1)), m2.start(), m2.end(), 0.7))

    def _shifts(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        sh = self.lex["shifts"]
        all_hits = find_terms(folded, _terms(sh["all"], lang), lang)
        if all_hits:
            s, e, _ = all_hits[0]
            r.facts.append(Fact("shifts", {"early": True, "late": True, "night": True, "weekend": True}, s, e))
            return
        context = ["schicht", "dienst", "shift", "vardiya", "zmian", "tura", "ture", "змін", "смен", "وردي"]
        has_context = asked == "shifts" or any(c in folded for c in context)
        negation = _terms(sh["negation"], lang, mix=False)
        values: dict[str, bool] = {}
        span: list[int] = []
        for name, by_lang in sh["names"].items():
            for s, e, term in find_terms(folded, _terms(by_lang, lang), lang):
                short = len(term) <= 6 and " " not in term and not any(c in term for c in context)
                if short and not has_context:
                    continue
                before = folded[max(0, s - 22) : s]
                after = folded[e : e + 14]
                neg = (
                    contains_any(before, negation, lang)
                    or (lang == "tr" and contains_any(after, negation, lang))
                    or bool(re.match(r"\s*(?:nein|no|nie|nu|ні|нет|لا)\b", after))
                )
                values[name] = not neg
                span += [s, e]
                break
        if values:
            # "only early shift": the shifts not named are refused
            before_first = folded[max(0, min(span) - 16) : min(span)]
            only = _terms(sh["only"], lang)
            after_last = folded[max(span) : max(span) + 10]
            if any(v for v in values.values()) and (contains_any(before_first, only, lang) or contains_any(after_last, only, lang)):
                for name in ("early", "late", "night"):
                    values.setdefault(name, False)
            r.facts.append(Fact("shifts", values, min(span), max(span)))

    def _start(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        lex = self.lex
        hits = find_terms(folded, _terms(lex["immediately"], lang), lang)
        if hits:
            s, e, _ = hits[0]
            r.facts.append(Fact("start_date", today.isoformat(), s, e))
            return
        m = _DATE_ISO.search(text)
        if m:
            r.facts.append(Fact("start_date", date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat(), m.start(), m.end()))
            return
        for m in _DATE_NUM.finditer(text):
            d, mo = int(m.group(1)), int(m.group(2))
            if not (1 <= d <= 31 and 1 <= mo <= 12):
                continue
            y = int(m.group(3)) if m.group(3) else today.year
            y = y + 2000 if y < 100 else y
            try:
                when = date(y, mo, d)
            except ValueError:
                continue
            if not m.group(3) and when < today:
                when = date(y + 1, mo, d)
            r.facts.append(Fact("start_date", when.isoformat(), m.start(), m.end()))
            return
        nm = find_terms(folded, _terms(lex["next_month"], lang), lang)
        if nm:
            first = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
            r.facts.append(Fact("start_date", first.isoformat(), nm[0][0], nm[0][1]))
            return
        # "in 2 Wochen", "Kündigungsfrist 3 Monate", "za 2 tygodnie", "через 2 недели"
        units = lex["relative_units"]
        for m in _NUMBER.finditer(folded):
            n = int(m.group(1))
            tail = folded[m.end() : m.end() + 14]
            for unit, days in (("week", 7), ("month", 30)):
                u = find_terms(tail, _terms(units[unit], lang), lang)
                if u and u[0][0] <= 2 and 0 < n <= 12:
                    # not experience ("5 years") and not a past duration ("seit 3 Monaten")
                    if contains_any(folded[max(0, m.start() - 8) : m.start()], _SINCE, lang):
                        continue
                    r.facts.append(Fact("start_date", (today + timedelta(days=n * days)).isoformat(), m.start(), m.end() + u[0][1], 0.75))
                    return
        months = lex["months"]
        names = {fold(k): v for k, v in {**months.get(lang, {}), **months["de"], **months["en"]}.items()}
        for s, e, term in find_terms(folded, list(names), None):
            if len(term) < 3 and term not in ("mai", "may"):
                continue
            mo = names[term]
            day_m = re.search(r"(\d{1,2})\.?\s*$", folded[max(0, s - 6) : s])
            day = int(day_m.group(1)) if day_m and 1 <= int(day_m.group(1)) <= 31 else 1
            y = today.year + (1 if (mo, day) < (today.month, today.day) else 0)
            with contextlib.suppress(ValueError):
                r.facts.append(Fact("start_date", date(y, mo, day).isoformat(), s, e, 0.8))
            return
        # Polish/Ukrainian/Russian month stems inflect ("od marca", "з березня"): prefix search
        if lang in ("pl", "uk", "ru"):
            for stem, mo in months.get(lang, {}).items():
                m2 = re.search(r"(?<![\w])" + re.escape(fold(stem)) + r"\w*", folded)
                if m2:
                    y = today.year + (1 if mo < today.month else 0)
                    r.facts.append(Fact("start_date", date(y, mo, 1).isoformat(), m2.start(), m2.end(), 0.7))
                    return

    def _german(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        context = _terms(self.lex["german_context"], lang)
        licence = _terms(self.lex["licence_context"], lang)
        for m in re.finditer(r"(?<![\w])([abcABC][12])(?![\w])", text):
            lvl = m.group(1).upper()
            near_german = _near(folded, m.start(), m.end(), context, lang, 30, 25)
            near_licence = _near(folded, m.start(), m.end(), licence, lang, 20, 10)
            if lvl == "C1" and near_licence and _gap(folded, m.start(), m.end(), licence, lang) <= _gap(folded, m.start(), m.end(), context, lang):
                continue  # "Führerschein C1": the lorry class, not a language level
            if near_german or (asked == "german_level" and not near_licence):
                r.facts.append(Fact("german_level", lvl, m.start(), m.end()))
                return
        words = self.lex["german_words"]
        for key in ("none", "fluent", "good", "basic"):
            hits = find_terms(folded, _terms(words[key], lang), lang)
            if hits:
                s, e, _ = hits[0]
                r.facts.append(Fact("german_level", LEVEL_WORDS[key], s, e, 0.75))
                return

    def _experience(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        units = _terms(self.lex["experience_units"], lang)
        context = _terms(self.lex["experience_context"], lang)
        for m in _NUMBER.finditer(folded):
            n = int(m.group(1))
            tail = folded[m.end() : m.end() + 12]
            u = find_terms(tail, units, lang)
            if not u or u[0][0] > 2 or n > 50:
                continue
            end = m.end() + u[0][1]
            if _near(folded, m.start(), end, _AGE_WORDS, lang, 10, 12):
                continue  # an age, deliberately not recorded
            since = contains_any(folded[max(0, m.start() - 8) : m.start()], _SINCE, lang)
            if since or _near(folded, m.start(), end, context, lang, 40, 40) or asked == "experience_years":
                r.facts.append(Fact("experience_years", n, m.start(), end))
                return
        for m in _YEAR.finditer(folded):
            y = int(m.group(1))
            since = contains_any(folded[max(0, m.start() - 8) : m.start()], _SINCE, lang) and y <= today.year
            if since and (_near(folded, m.start(), m.end(), context, lang, 40, 40) or asked == "experience_years" or r.get("occupation") is not None):
                r.facts.append(Fact("experience_years", today.year - y, m.start(), m.end(), 0.8))
                return
        if asked == "experience_years":
            m3 = _NUMBER.search(folded)
            if m3 and int(m3.group(1)) <= 50:
                r.facts.append(Fact("experience_years", int(m3.group(1)), m3.start(), m3.end(), 0.7))

    def _employment(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        emp = self.lex["employment"]
        values = []
        span: list[int] = []
        for key in ("full_time", "part_time"):
            hits = find_terms(folded, _terms(emp[key], lang), lang)
            if hits:
                values.append(key)
                span += list(hits[0][:2])
        if values:
            r.facts.append(Fact("employment", values, min(span), max(span)))

    def _email(self, text: str, folded: str, lang: str, today: date, asked: Any, r: Reading) -> None:
        m = _EMAIL.search(text)
        if m:
            r.facts.append(Fact("email", m.group(0).lower(), m.start(), m.end()))

    def _full_name(self, text: str, r: Reading) -> None:
        words = re.findall(r"[^\W\d_][\w'’-]*", text)
        if 2 <= len(words) <= 4 and len(text) <= 60:
            m = re.search(re.escape(words[0]) + r".*" + re.escape(words[-1]), text)
            if m:
                r.facts.append(Fact("full_name", " ".join(words), m.start(), m.end(), 0.8))
