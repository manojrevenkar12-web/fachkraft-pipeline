"""Matching a candidate to jobs, with the reason for every verdict.

Hard requirements decide whether a candidate fits: occupation, recognition for regulated
occupations, licences, commute, shifts, start date, a justified German level. A requirement the
candidate has not answered is "unknown", not a failure. A gap that is usually closed within weeks
(Code 95, a forklift licence, a recognition procedure under way) makes a near match that a
recruiter decides on, instead of a rejection.

Matching reads only the fields in `matching.feature_allowlist`. Name, phone number, email and the
language the candidate wrote in are not passed in at all, so the result cannot depend on them;
`tests/test_matching.py` checks that by changing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import config, geo
from .jobs import CEFR_RANK, Job

PASS, FAIL, UNKNOWN, FIXABLE = "pass", "fail", "unknown", "fixable"


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Match:
    job_id: str
    verdict: str  # fit, near, unknown, no
    score: float
    checks: list[Check] = field(default_factory=list)
    distance_km: float | None = None

    @property
    def gaps(self) -> list[str]:
        return [c.detail for c in self.checks if c.status in (FAIL, FIXABLE)]

    @property
    def unknowns(self) -> list[str]:
        return [c.name for c in self.checks if c.status == UNKNOWN]

    def to_dict(self) -> dict[str, Any]:
        return {"job_id": self.job_id, "verdict": self.verdict, "score": round(self.score, 3), "distance_km": None if self.distance_km is None else round(self.distance_km, 1),
                "checks": [c.__dict__ for c in self.checks]}


def features(profile: dict[str, Any]) -> dict[str, Any]:
    """The only view of a profile matching ever sees."""
    allow = set(config.settings()["matching"]["feature_allowlist"])
    return {k: v for k, v in profile.items() if k in allow}


def _place(loc: Any) -> geo.Place | None:
    if isinstance(loc, dict) and "lat" in loc:
        return geo.Place(loc.get("place", ""), loc.get("plz", ""), float(loc["lat"]), float(loc["lon"]))
    return None


def match(job: Job, profile_values: dict[str, Any], today: date) -> Match:
    f = features(profile_values)
    st = config.settings()["matching"]
    checks: list[Check] = []

    occ = f.get("occupation")
    if occ is None:
        checks.append(Check("occupation", UNKNOWN, "occupation not given"))
    elif job.occupation in occ:
        checks.append(Check("occupation", PASS, job.occupation))
    else:
        checks.append(Check("occupation", FAIL, f"works as {', '.join(occ)}, job needs {job.occupation}"))

    if job.needs_recognition:
        qual, rec = f.get("qualification"), f.get("recognition")
        if qual == "domestic" or rec == "recognised":
            checks.append(Check("recognition", PASS, "German or recognised qualification"))
        elif qual == "none":
            checks.append(Check("recognition", FAIL, "no qualification in the occupation"))
        elif rec == "in_progress":
            checks.append(Check("recognition", FIXABLE, "recognition procedure under way"))
        elif rec == "not_started":
            checks.append(Check("recognition", FIXABLE, "foreign qualification not yet recognised"))
        else:
            checks.append(Check("recognition", UNKNOWN, "recognition status not given"))

    need = list(job.must.get("licences", []))
    if need:
        have = f.get("licences")
        if have is None:
            checks.append(Check("licences", UNKNOWN, "licences not given"))
        else:
            missing = [x for x in need if x not in have]
            fixable = set(st["fixable_gaps"])
            if not missing:
                checks.append(Check("licences", PASS, ", ".join(need)))
            elif all(x in fixable for x in missing):
                checks.append(Check("licences", FIXABLE, f"missing {', '.join(missing)}"))
            else:
                checks.append(Check("licences", FAIL, f"missing {', '.join(missing)}"))

    dist = None
    home = _place(f.get("location"))
    if home is None:
        checks.append(Check("commute", UNKNOWN, "home not given"))
    else:
        dist = geo.km(home, job.place)
        limit = min(job.radius_km, f["commute_km"]) if f.get("commute_km") else job.radius_km
        if dist <= limit:
            checks.append(Check("commute", PASS, f"{dist:.0f} km"))
        else:
            checks.append(Check("commute", FAIL, f"{dist:.0f} km, limit {limit} km"))

    if job.shifts:
        cand = f.get("shifts")
        if cand is None:
            checks.append(Check("shifts", UNKNOWN, "shifts not given"))
        else:
            refused = [s for s in job.shifts if cand.get(s) is False]
            if refused:
                checks.append(Check("shifts", FAIL, f"does not work {', '.join(refused)}"))
            else:
                checks.append(Check("shifts", PASS, ", ".join(job.shifts)))

    start = f.get("start_date")
    if start is None:
        checks.append(Check("start", UNKNOWN, "start date not given"))
    else:
        when = date.fromisoformat(start)
        late = (when - job.start_by).days
        if late <= 0:
            checks.append(Check("start", PASS, when.isoformat()))
        elif late <= st["start_grace_days"]:
            checks.append(Check("start", FIXABLE, f"starts {when.isoformat()}, {late} days after {job.start_by.isoformat()}"))
        else:
            checks.append(Check("start", FAIL, f"starts {when.isoformat()}, job needs someone by {job.start_by.isoformat()}"))

    level = job.german_min
    if level:
        g = f.get("german_level")
        if g is None:
            checks.append(Check("german", UNKNOWN, "German level not given"))
        elif CEFR_RANK.get(g, 0) >= CEFR_RANK[level]:
            checks.append(Check("german", PASS, f"{g} (needs {level})"))
        elif CEFR_RANK.get(g, 0) == CEFR_RANK[level] - 1:
            checks.append(Check("german", FIXABLE, f"German {g}, job needs {level}"))
        else:
            checks.append(Check("german", FAIL, f"German {g}, job needs {level}"))

    emp = f.get("employment")
    if emp and not set(emp) & set(job.employment):
        checks.append(Check("employment", FAIL, f"wants {', '.join(emp)}"))

    statuses = {c.status for c in checks}
    if FAIL in statuses:
        verdict = "no"
    elif UNKNOWN in statuses:
        verdict = "unknown"
    elif FIXABLE in statuses:
        verdict = "near"
    else:
        verdict = "fit"
    w = st["weights"]
    s_dist = 1 - min(1.0, (dist or job.radius_km) / max(job.radius_km, 1))
    exp = f.get("experience_years")
    want = job.soft.get("experience_years", 0) or 0
    s_exp = 0.5 if exp is None else min(1.0, (exp + 1) / (want + 1))
    s_shift = 1.0 if f.get("shifts") and all(f["shifts"].get(s, True) for s in job.shifts) else 0.5
    if start:
        delay = max(0, (date.fromisoformat(start) - today).days)
        s_start = 1 - min(1.0, delay / st["max_start_delay_days"])
    else:
        s_start = 0.5
    score = w["distance"] * s_dist + w["experience"] * s_exp + w["shifts"] * s_shift + w["start"] * s_start
    return Match(job.id, verdict, score, checks, dist)


def rank(jobs: list[Job], profile_values: dict[str, Any], today: date) -> list[Match]:
    order = {"fit": 0, "near": 1, "unknown": 2, "no": 3}
    ms = [match(j, profile_values, today) for j in jobs if j.open]
    return sorted(ms, key=lambda m: (order[m.verdict], -m.score))
