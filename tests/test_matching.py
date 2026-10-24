from datetime import date

import pytest

from fkp import geo, matching

TODAY = date(2026, 10, 26)


def loc(plz):
    p = geo.by_plz(plz)
    return {"place": p.name, "plz": p.plz, "lat": p.lat, "lon": p.lon}


@pytest.fixture
def driver():
    return {
        "occupation": ["berufskraftfahrer"],
        "licences": ["B", "C", "CE", "code95"],
        "location": loc("04315"),
        "start_date": "2026-12-01",
        "shifts": {"early": True, "late": True, "night": False},
        "experience_years": 8,
    }


def job(demo_jobs, jid):
    return next(j for j in demo_jobs if j.id == jid)


def test_fit_with_reasons(demo_jobs, driver):
    m = matching.match(job(demo_jobs, "J-LKW-LEJ"), driver, TODAY)
    assert m.verdict == "fit" and m.distance_km < 10
    assert {c.name: c.status for c in m.checks} == {"occupation": "pass", "licences": "pass", "commute": "pass", "shifts": "pass", "start": "pass"}


def test_missing_code95_is_a_near_match_and_missing_ce_is_not(demo_jobs, driver):
    d = {**driver, "licences": ["B", "C", "CE"]}
    assert matching.match(job(demo_jobs, "J-LKW-LEJ"), d, TODAY).verdict == "near"
    d = {**driver, "licences": ["B", "C"]}
    assert matching.match(job(demo_jobs, "J-LKW-LEJ"), d, TODAY).verdict == "no"


def test_refused_shift_and_distance_fail(demo_jobs, driver):
    lager = {**driver, "occupation": ["lagerlogistik"], "licences": ["forklift"], "location": loc("44135"), "shifts": {"night": False}}
    m = matching.match(job(demo_jobs, "J-LAG-DO"), lager, TODAY)
    assert m.verdict == "no" and "night" in m.gaps[0]
    far = {**driver, "location": loc("80331")}
    assert matching.match(job(demo_jobs, "J-LKW-LEJ"), far, TODAY).verdict == "no"


def test_recognition_for_regulated_occupations(demo_jobs):
    nurse = {"occupation": ["pflegefachkraft"], "location": loc("10247"), "start_date": "2026-11-15", "shifts": {"early": True}, "german_level": "B2"}
    j = job(demo_jobs, "J-PFK-BER")
    assert matching.match(j, {**nurse, "qualification": "domestic"}, TODAY).verdict == "fit"
    assert matching.match(j, {**nurse, "qualification": "foreign", "recognition": "in_progress"}, TODAY).verdict == "near"
    assert matching.match(j, {**nurse, "qualification": "foreign"}, TODAY).verdict == "unknown"
    assert matching.match(j, {**nurse, "qualification": "none"}, TODAY).verdict == "no"


def test_german_level_filters_only_with_a_reason(demo_jobs):
    j = job(demo_jobs, "J-ELE-MUC")
    sparky = {"occupation": ["elektroniker"], "location": loc("80331"), "start_date": "2026-11-01", "shifts": {"early": True}}
    assert matching.match(j, {**sparky, "german_level": "A1"}, TODAY).verdict == "no"
    assert matching.match(j, {**sparky, "german_level": "A2"}, TODAY).verdict == "near"
    j.german_level = {"min": "B1", "justification": ""}
    try:
        assert matching.match(j, {**sparky, "german_level": "A1"}, TODAY).verdict == "fit"
    finally:
        j.german_level = {"min": "B1", "justification": "Sicherheitsunterweisungen auf der Baustelle"}


def test_start_a_little_late_is_near(demo_jobs, driver):
    j = job(demo_jobs, "J-LKW-LEJ")  # start by 2027-01-31
    assert matching.match(j, {**driver, "start_date": "2027-02-20"}, TODAY).verdict == "near"
    assert matching.match(j, {**driver, "start_date": "2027-06-01"}, TODAY).verdict == "no"


def test_result_cannot_depend_on_name_language_or_contact(demo_jobs, driver):
    """Counterfactual check: change everything matching must not see; the result is identical."""
    base = [m.to_dict() for m in matching.rank(demo_jobs, driver, TODAY)]
    for extra in (
        {"full_name": "Mehmet Yılmaz", "email": "m@x.example"},
        {"full_name": "Hans Müller", "lang": "ar", "phone": "+491700000"},
        {"nationality": "SY", "age": 52, "religion": "x"},
    ):
        assert [m.to_dict() for m in matching.rank(demo_jobs, {**driver, **extra}, TODAY)] == base
    assert set(matching.features({**driver, "full_name": "x", "age": 3})) == set(driver)
