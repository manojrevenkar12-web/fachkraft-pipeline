"""Run a blind-written held-out set and keep its first run.

Two kinds of set (see heldout/WRITING_*.md):

* `cases.yaml`: candidate messages with the facts they state. Scored per field: a value is right,
  wrong, or missed; anything read that the message does not state is a false reading.
* `ads.yaml`: job ads with the AGG problems they contain. Scored per problem id and on the
  publish/block decision.

The first run of a set is written to `reports/heldout/<set>/first_run.json` and never overwritten;
later runs go to `latest.json`. A set whose `STATUS` says `regression` has been studied, so its
numbers are labelled as such.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import config, geo, jobs as jobs_mod, lang as lang_mod, privacy
from .extract import RuleExtractor
from .extract.rules import _IMPLIED

REPORTS = config.ROOT / "reports" / "heldout"
INTENT = {"stop": "opt_out", "human": "human", "yes": "yes", "no": "no"}


def _closure(xs: list[str]) -> set[str]:
    out = set(xs)
    for x in list(out):
        out |= _IMPLIED.get(x, set())
    return out


def _where(v: dict[str, Any]) -> geo.Place | None:
    if v.get("plz"):
        p = geo.by_plz(str(v["plz"]))
        if p:
            return p
    if v.get("place"):
        return geo.by_name(str(v["place"]))
    return None


def right(field: str, got: Any, want: Any, today: date) -> bool:
    """Is a read value the labelled one? Lenient only where the guide says so."""
    if field == "occupation":
        return set(want) <= set(got or []) and len(set(got or []) - set(want)) == 0
    if field == "licences":
        return _closure(list(got or [])) == _closure(list(want or []))
    if field == "location":
        if not isinstance(got, dict):
            return False
        if want.get("plz") and str(want["plz"]) == got.get("plz"):
            return True
        w = _where(want)
        return bool(w and geo.km(w, geo.Place("", "", got["lat"], got["lon"])) <= 15)
    if field == "commute_km":
        return isinstance(got, int | float) and abs(got - want) <= 0.4 * max(want, 1)
    if field == "shifts":
        return isinstance(got, dict) and all(got.get(k) == v for k, v in want.items())
    if field == "start_date":
        return str(got) == str(want)
    if field in ("employment",):
        return set(got or []) == set(want or [])
    if field == "full_name":
        return " ".join(str(got).split()).lower() == " ".join(str(want).split()).lower()
    if field == "email":
        return str(got).lower() == str(want).lower()
    return bool(got == want)


def _messages(set_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    x = RuleExtractor()
    today = date.fromisoformat(str(data["today"]))
    per: dict[str, dict[str, int]] = defaultdict(lambda: {"right": 0, "wrong": 0, "missed": 0, "false": 0})
    by_lang: dict[str, dict[str, int]] = defaultdict(lambda: {"right": 0, "wrong": 0, "missed": 0, "false": 0, "cases": 0, "exact": 0})
    intents = {"right": 0, "missed": 0, "false": 0}
    health = {"right": 0, "missed": 0, "false": 0}
    lang_ok = 0
    failures = []
    cases = data["cases"]
    for c in cases:
        lang = lang_mod.detect(c["text"], default=c.get("lang", "de"))
        lang_ok += lang == c.get("lang")
        reading = x.read(c["text"], lang, today, c.get("asked"))
        got: dict[str, Any] = {}
        for f in reading.facts:
            got.setdefault(f.field, f.value)
        want = {k: v for k, v in (c.get("expect") or {}).items()}
        if "start_date" in want:
            want["start_date"] = str(want["start_date"])
        bl = by_lang[c.get("lang", "?")]
        bl["cases"] += 1
        problems = []
        for k, v in want.items():
            if k not in got:
                per[k]["missed"] += 1
                bl["missed"] += 1
                problems.append(f"missed {k}")
            elif right(k, got[k], v, today):
                per[k]["right"] += 1
                bl["right"] += 1
            else:
                per[k]["wrong"] += 1
                bl["wrong"] += 1
                problems.append(f"wrong {k}")
        for k in got:
            if k not in want:
                per[k]["false"] += 1
                bl["false"] += 1
                problems.append(f"false {k}")
        want_i = {INTENT.get(i, i) for i in (c.get("intents") or [])}
        for i in want_i:
            intents["right" if i in reading.intents else "missed"] += 1
            if i not in reading.intents:
                problems.append(f"missed intent {i}")
        for i in set(reading.intents) - want_i:
            if i in ("opt_out", "human"):  # yes/no are read only where a yes/no is expected
                intents["false"] += 1
                problems.append(f"false intent {i}")
        h_want, h_got = bool(c.get("health")), privacy.mentions_health(c["text"], lang)
        if h_want:
            health["right" if h_got else "missed"] += 1
        elif h_got:
            health["false"] += 1
        if h_want and not h_got:
            problems.append("health not redacted")
        if not problems:
            bl["exact"] += 1
        else:
            failures.append({"id": c["id"], "problems": problems})

    def prf(d: dict[str, int]) -> dict[str, Any]:
        tp, wrong, miss, fp = d["right"], d["wrong"], d["missed"], d["false"]
        precision = tp / (tp + wrong + fp) if tp + wrong + fp else None
        recall = tp / (tp + wrong + miss) if tp + wrong + miss else None
        return {**d, "precision": None if precision is None else round(precision, 3), "recall": None if recall is None else round(recall, 3)}

    total = {k: sum(d[k] for d in per.values()) for k in ("right", "wrong", "missed", "false")}
    exact = sum(d["exact"] for d in by_lang.values())
    res = {
        "kind": "messages", "cases": len(cases), "today": str(today), "extractor": "rules",
        "overall": prf(total), "exact_cases": exact, "exact_rate": round(exact / len(cases), 3) if cases else None,
        "language_detected": round(lang_ok / len(cases), 3) if cases else None,
        "fields": {k: prf(v) for k, v in sorted(per.items())},
        "by_language": {k: {**prf(v), "cases": v["cases"], "exact": v["exact"]} for k, v in sorted(by_lang.items())},
        "intents": intents, "health": health, "failures": failures,
    }
    return res


def _ads(set_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    per: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0})
    block_rules = jobs_mod.block_rules()
    decision = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    failures = []
    for ad in data["ads"]:
        got = {i.rule for i in jobs_mod.check_agg(ad)}
        want = set(ad.get("expect") or [])
        for r in want | got:
            if r in want and r in got:
                per[r]["tp"] += 1
            elif r in want:
                per[r]["fn"] += 1
            else:
                per[r]["fp"] += 1
        w_block, g_block = bool(want & block_rules), bool(got & block_rules)
        decision["tp" if w_block and g_block else "fn" if w_block else "fp" if g_block else "tn"] += 1
        if want != got:
            failures.append({"id": ad["id"], "missed": sorted(want - got), "false": sorted(got - want)})

    def prf(d: dict[str, int]) -> dict[str, Any]:
        p = d["tp"] / (d["tp"] + d["fp"]) if d["tp"] + d["fp"] else None
        r = d["tp"] / (d["tp"] + d["fn"]) if d["tp"] + d["fn"] else None
        return {**d, "precision": None if p is None else round(p, 3), "recall": None if r is None else round(r, 3)}

    total = {k: sum(v[k] for v in per.values()) for k in ("tp", "fn", "fp")}
    n = len(data["ads"])
    return {"kind": "jobads", "ads": n, "overall": prf(total), "rules": {k: prf(v) for k, v in sorted(per.items())},
            "block_decision": {**decision, "accuracy": round((decision["tp"] + decision["tn"]) / n, 3) if n else None},
            "exact_ads": n - len(failures), "failures": failures}


def run(set_dir: Path | str) -> dict[str, Any]:
    d = Path(set_dir)
    status = (d / "STATUS").read_text().strip() if (d / "STATUS").exists() else "heldout"
    if (d / "cases.yaml").exists():
        res = _messages(d, yaml.safe_load((d / "cases.yaml").read_text(encoding="utf-8")))
    elif (d / "ads.yaml").exists():
        res = _ads(d, yaml.safe_load((d / "ads.yaml").read_text(encoding="utf-8")))
    else:
        raise FileNotFoundError(f"{d}: neither cases.yaml nor ads.yaml")
    res["set"] = d.name
    res["status"] = status
    res["markdown"] = markdown(res)
    return res


def record(res: dict[str, Any], reports: Path | None = None) -> tuple[Path, bool]:
    """Write the first run once; every later run goes to latest.json."""
    base = (reports or Path(os.environ.get("FKP_HELDOUT_REPORTS", REPORTS))) / res["set"]
    base.mkdir(parents=True, exist_ok=True)
    first = base / "first_run.json"
    body = json.dumps({k: v for k, v in res.items() if k != "markdown"}, indent=2, ensure_ascii=False, default=str) + "\n"
    if not first.exists():
        first.write_text(body)
        (base / "FIRST_RUN.md").write_text(res["markdown"])
        return first, True
    latest = base / "latest.json"
    latest.write_text(body)
    return latest, False


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def markdown(r: dict[str, Any]) -> str:
    label = "held-out (blind, first run)" if r.get("status") == "heldout" else f"{r.get('status')} (studied; not an unbiased number)"
    if r["kind"] == "messages":
        o = r["overall"]
        lines = [f"# {r['set']}: candidate messages, {label}", "",
                 f"{r['cases']} messages read with the offline rules (no model). Precision counts wrong and invented values against the reader; "
                 "recall counts wrong and missed values.", "",
                 f"Precision {_pct(o['precision'])}, recall {_pct(o['recall'])}; {r['exact_cases']} of {r['cases']} messages read exactly "
                 f"({_pct(r['exact_rate'])}); language detected right {_pct(r['language_detected'])}.", "",
                 f"Intents (stop, human, yes, no): {r['intents']['right']} right, {r['intents']['missed']} missed, {r['intents']['false']} false. "
                 f"Health mentions redacted: {r['health']['right']} of {r['health']['right'] + r['health']['missed']}, {r['health']['false']} false.", "",
                 "| Field | Right | Wrong | Missed | Invented | Precision | Recall |", "|---|---:|---:|---:|---:|---:|---:|"]
        for k, v in r["fields"].items():
            lines.append(f"| {k} | {v['right']} | {v['wrong']} | {v['missed']} | {v['false']} | {_pct(v['precision'])} | {_pct(v['recall'])} |")
        lines += ["", "| Language | Messages | Exact | Precision | Recall |", "|---|---:|---:|---:|---:|"]
        for k, v in r["by_language"].items():
            lines.append(f"| {k} | {v['cases']} | {v['exact']} | {_pct(v['precision'])} | {_pct(v['recall'])} |")
        return "\n".join(lines) + "\n"
    o, d = r["overall"], r["block_decision"]
    lines = [f"# {r['set']}: job ads, {label}", "",
             f"{r['ads']} ads. Problems found: precision {_pct(o['precision'])}, recall {_pct(o['recall'])}. "
             f"{r['exact_ads']} ads with exactly the labelled problems.", "",
             f"Publish/block decision: {_pct(d['accuracy'])} right ({d['tp']} blocked rightly, {d['tn']} published rightly, "
             f"{d['fn']} published that should have been blocked, {d['fp']} blocked that were fine).", "",
             "| Problem | Found | Missed | False | Precision | Recall |", "|---|---:|---:|---:|---:|---:|"]
    for k, v in r["rules"].items():
        lines.append(f"| {k} | {v['tp']} | {v['fn']} | {v['fp']} | {_pct(v['precision'])} | {_pct(v['recall'])} |")
    return "\n".join(lines) + "\n"
