"""The simulation: reproducible, and the comparisons it reports hold on a small run."""

from fkp.sim import evaluate, personas
from fkp.sim.run import same


def test_personas_are_reproducible_and_cover_the_languages():
    a = personas.make(80, 3, evaluate.START.date())
    b = personas.make(80, 3, evaluate.START.date())
    assert [p.truth for p in a] == [p.truth for p in b]
    assert {p.lang for p in a} >= {"de", "tr", "pl", "ro"}
    assert all(p.truth["email"].endswith(".example") for p in a)


def test_small_run_report_is_deterministic_and_says_it_is_a_simulation():
    r1 = evaluate.run(n=80, seed=11)
    r2 = evaluate.run(n=80, seed=11)
    assert r1 == r2 and r1["kind"] == "simulation"
    md = evaluate.markdown(r1)
    assert "This is a simulation" in md and "heldout" in md


def test_assistant_needs_fewer_messages_and_forwards_fewer_wrong_candidates():
    r = evaluate.run(n=150, seed=5)
    a, f, m = r["assistant"], r["form_bot"], r["matching"]
    assert a["median_replies_when_completed"] < f["median_replies_when_completed"]
    assert m["assistant"]["precision"] > m["keyword"]["precision"]
    assert r["language_detected_right"] > 0.95


def test_comparison_rules():
    assert same("shifts", {"early": True, "late": False, "night": False, "weekend": True}, {"early": True, "late": False, "night": False})
    assert not same("shifts", {"early": True}, {"early": True, "late": False, "night": False})
    assert same("start_date", "2026-10-29", "2026-10-26", start_now=True)
    assert not same("licences", ["B", "C1"], ["B"])
