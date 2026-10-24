"""Where a candidate lives, and how far that is from a job.

Postcodes and place coordinates come from GeoNames (CC BY 4.0) via data/geo/de_postcodes.csv.
Larger cities are recognised by name in any supported language (config/cities.yaml); every other
place by postcode, or by its exact name right after a location word ("in", "aus", "w", "в", ...).
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from . import config
from .text import find_terms, fold

PLZ = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_MONEY_AFTER = re.compile(r"^\s*(?:€|eur|euro|brutto|netto|\$)", re.I)
_LOCATION_WORDS = [
    "in",
    "aus",
    "bei",
    "nähe",
    "nahe",
    "near",
    "from",
    "w",
    "z",
    "pod",
    "în",
    "din",
    "lângă",
    "в",
    "у",
    "з",
    "из",
    "під",
    "под",
    "في",
    "من",
    "قرب",
    "wohne in",
    "lebe in",
    "live in",
    "mieszkam w",
    "locuiesc în",
    "живу в",
    "живу у",
    "أسكن في",
]


@dataclass(frozen=True)
class Place:
    name: str
    plz: str
    lat: float
    lon: float


@lru_cache(maxsize=1)
def _postcodes() -> dict[str, Place]:
    out = {}
    with (config.DATA_DIR / "geo" / "de_postcodes.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["plz"]] = Place(r["place"], r["plz"], float(r["lat"]), float(r["lon"]))
    return out


@lru_cache(maxsize=1)
def _places_by_name() -> dict[str, Place]:
    by: dict[str, list[Place]] = {}
    for p in _postcodes().values():
        by.setdefault(fold(p.name), []).append(p)
    out = {}
    for name, ps in by.items():
        lat = sum(p.lat for p in ps) / len(ps)
        lon = sum(p.lon for p in ps) / len(ps)
        out[name] = Place(ps[0].name, sorted(p.plz for p in ps)[0], round(lat, 4), round(lon, 4))
    return out


@lru_cache(maxsize=1)
def _cities() -> dict[str, Place]:
    """folded alias -> Place"""
    pcs = _postcodes()
    out = {}
    for canonical, spec in config.load("cities").items():
        p = pcs[spec["plz"]]
        place = Place(canonical, p.plz, p.lat, p.lon)
        for alias in spec["names"]:
            out[fold(alias)] = place
    return out


def by_plz(plz: str) -> Place | None:
    return _postcodes().get(plz)


def by_name(name: str) -> Place | None:
    """A town by its name (any listed exonym or the gazetteer name)."""
    key = fold(name.strip())
    return _cities().get(key) or _places_by_name().get(key)


def find(text: str, lang: str) -> tuple[Place, int, int] | None:
    """The place a message names, with its span; postcodes win over names."""
    folded = fold(text)
    for m in PLZ.finditer(text):
        if _MONEY_AFTER.match(text[m.end() :]):
            continue
        p = by_plz(m.group(1))
        if p:
            return p, m.start(1), m.end(1)
    cities = _cities()
    hits = find_terms(folded, list(cities), lang if lang in ("tr", "pl", "ro", "uk", "ru") else None)
    if hits:
        s, e, term = hits[0]
        return cities[term], s, e
    # any GeoNames place, but only right after a location word, to keep "Essen" (food) and "Hof"
    # (yard) from being read as towns
    names = _places_by_name()
    loc = "|".join(re.escape(fold(w)) for w in sorted(_LOCATION_WORDS, key=len, reverse=True))
    for m in re.finditer(r"(?<![\w])(?:" + loc + r")\s+", folded):
        start = m.end()
        if start >= len(text) or not text[start].isupper():
            continue
        words = re.findall(r"[^\s,;:!?]+", folded[start : start + 60])[:4]
        for n in range(len(words), 0, -1):
            cand = " ".join(words[:n]).strip(".")
            if cand in names:
                return names[cand], start, start + len(cand)
    return None


def km(a: Place, b: Place) -> float:
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
