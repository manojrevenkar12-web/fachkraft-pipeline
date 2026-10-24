"""The held-out runner, on a tiny set written for this test (the real sets are blind)."""

from pathlib import Path

from fkp import heldout

FIX = Path(__file__).parent / "fixtures" / "heldout"


def test_messages_scoring_counts_right_missed_and_intents():
    r = heldout.run(FIX / "msgs")
    assert r["kind"] == "messages" and r["cases"] == 5
    assert r["fields"]["occupation"]["right"] == 2 and r["fields"]["location"]["missed"] == 1
    assert r["fields"]["shifts"]["right"] == 1 and r["fields"]["licences"]["right"] == 1
    assert r["intents"]["right"] == 1
    assert {f["id"] for f in r["failures"]} == {"e"}
    assert "held-out" in r["markdown"]


def test_ads_scoring_and_block_decision():
    r = heldout.run(FIX / "ads")
    assert r["rules"]["age"]["tp"] == 1 and r["rules"]["photo"]["fn"] == 1
    assert r["block_decision"]["tp"] == 2 and r["block_decision"]["tn"] == 2


def test_first_run_is_never_rewritten(tmp_path):
    r = heldout.run(FIX / "ads")
    p1, first = heldout.record(r, tmp_path)
    before = p1.read_text()
    r["overall"]["precision"] = 0.0
    p2, again = heldout.record(r, tmp_path)
    assert first and not again and p1.read_text() == before and p2.name == "latest.json"
    assert (tmp_path / "ads" / "FIRST_RUN.md").exists()
