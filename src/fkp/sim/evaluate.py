"""`fkp eval`: simulated candidates with a hidden true profile, three ways of handling them.

1. The assistant (consent, open question, targeted questions, read-back, match, hand-over).
2. A fixed WhatsApp form bot that asks every field, one per message, and is assumed to read every
   answer perfectly.
3. Keyword forwarding (occupation title + city), the way a job board alert or a simple ATS filter
   passes candidates to a recruiter.

The numbers are a simulation: the drop-off and reminder assumptions are stated in the report, and
the candidate phrasings come from the same author as the extractor. They measure conversation
mechanics and matching logic, not reading accuracy on unseen text; for that see heldout/.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .. import config
from .. import jobs as jobs_mod
from . import personas
from .run import Assumptions, assistant, form_bot, keyword_forward, same, truth_matches

START = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)  # a Monday, 09:00 in Berlin
OUTCOME = {
    "handed_over": "handed to a recruiter",
    "pooled": "no job now, joined the talent pool",
    "deleted": "no job now, data deleted",
    "declined": "declined consent",
    "human": "asked for or passed to a person",
}
CHECK_FIELDS = ["occupation", "location", "qualification", "recognition", "licences", "start_date", "shifts", "german_level", "experience_years"]


def _rate(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def run(n: int = 600, seed: int = 7) -> dict[str, Any]:
    jobs = jobs_mod.load()
    a = Assumptions()
    ps = personas.make(n, seed, START.date())
    wa = config.settings()["whatsapp"]
    prices, currency = wa["prices"], wa["currency"]
    rows = []
    for p in ps:
        rows.append((p, assistant(p, jobs, START, a), form_bot(p, START, a), truth_matches(p, jobs, START.date()), keyword_forward(p, jobs)))

    def flow_stats(outs: list[Any]) -> dict[str, Any]:
        done = [o for o in outs if o.completed]
        return {
            "candidates": len(outs),
            "completed": len(done),
            "completion_rate": _rate(len(done), len(outs)),
            "median_replies_when_completed": statistics.median([o.replies for o in done]) if done else None,
            "median_minutes_to_done": round(statistics.median([o.minutes_to_done for o in done]), 1) if done else None,
            "reminders_free_form": sum(o.reminders_text for o in outs),
            "reminders_template": sum(o.reminders_template for o in outs),
            "service_messages": sum(o.sent + o.reminders_text for o in outs),
            # below 1,000 service messages a month only templates cost; above it every message does
            "cost_small": round(sum(o.reminders_template for o in outs) * prices["utility"], 2),
            "cost_at_volume": round(sum(o.reminders_template * prices["utility"] + (o.sent + o.reminders_text) * prices["service"] for o in outs), 2),
            "cost_at_volume_per_decision": round(
                sum(o.reminders_template * prices["utility"] + (o.sent + o.reminders_text) * prices["service"] for o in outs) / max(1, len(done)), 3
            ),
        }

    ast = [r[1] for r in rows]
    form = [r[2] for r in rows]
    report: dict[str, Any] = {
        "kind": "simulation",
        "seed": seed,
        "assumptions": {
            **asdict(a),
            "patience": "uniform 0.90–0.99 per prompt",
            "reply_delay": "80% minutes, 15% 1–6 h, 5% 10–18 h",
            "languages": personas.LANG_MIX,
            "prices": prices,
            "currency": currency,
        },
        "assistant": flow_stats(ast),
        "form_bot": flow_stats(form),
    }
    # stages the assistant ended in
    report["assistant"]["outcomes"] = dict(Counter(OUTCOME.get(o.stage, "stopped answering") for o in ast).most_common())

    # field accuracy of what reached the profile, against the hidden truth
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # right, wrong, missing
    lang_ok = 0
    for p, o, *_ in rows:
        if o.stage in ("new", "awaiting_consent", "declined"):
            continue
        lang_ok += o.detected_lang == p.lang
        if not o.completed:
            continue
        for f in CHECK_FIELDS:
            if f not in p.truth:
                continue
            if f not in o.profile:
                acc[f][2] += 1
            elif same(f, o.profile[f], p.truth[f], p.truth.get("_start_now", False)):
                acc[f][0] += 1
            else:
                acc[f][1] += 1
    report["fields"] = {
        f: {"right": r, "wrong": w, "not_asked_or_missing": m, "accuracy_when_present": _rate(r, r + w)} for f, (r, w, m) in acc.items()
    }
    total_r = sum(v[0] for v in acc.values())
    total_w = sum(v[1] for v in acc.values())
    report["field_accuracy_when_present"] = _rate(total_r, total_r + total_w)
    started = sum(1 for _, o, *_ in rows if o.stage not in ("new", "awaiting_consent", "declined"))
    report["language_detected_right"] = _rate(lang_ok, started)

    # matching: what reaches a recruiter, against what the true profile deserves
    def forward_quality(pairs: list[tuple[str, dict[str, str]]]) -> dict[str, Any]:
        good = sum(1 for j, t in pairs if t.get(j) in ("fit", "near"))
        return {"forwarded": len(pairs), "deserved": good, "precision": _rate(good, len(pairs))}

    ast_pairs = [(j, t) for p, o, _, t, _ in rows for j, _ in o.handed]
    kw_pairs = [(j, t) for p, _, _, t, kw in rows for j in kw]
    deserving = [(p, o, t) for p, o, _, t, _ in rows if any(v in ("fit", "near") for v in t.values())]
    found = sum(1 for p, o, t in deserving if any(t.get(j) in ("fit", "near") for j, _ in o.handed))
    kw_found = sum(1 for p, _, _, t, kw in rows if any(v in ("fit", "near") for v in t.values()) and any(t.get(j) in ("fit", "near") for j in kw))
    verdict_agree = sum(1 for p, o, _, t, _ in rows for j, v in o.handed if t.get(j) == v)
    report["matching"] = {
        "candidates_with_a_deserved_job": len(deserving),
        "assistant": {
            **forward_quality(ast_pairs),
            "candidates_reached": found,
            "recall": _rate(found, len(deserving)),
            "verdict_agrees_with_truth": _rate(verdict_agree, len(ast_pairs)),
        },
        "keyword": {**forward_quality(kw_pairs), "candidates_reached": kw_found, "recall": _rate(kw_found, len(deserving))},
    }

    # by language
    by: dict[str, dict[str, Any]] = {}
    for lg in personas.LANG_MIX:
        os_ = [o for _, o, *_ in rows if o.lang == lg]
        rr = [(p, o) for p, o, *_ in rows if o.lang == lg and o.completed]
        r = sum(
            1
            for p, o in rr
            for f in CHECK_FIELDS
            if f in p.truth and f in o.profile and same(f, o.profile[f], p.truth[f], p.truth.get("_start_now", False))
        )
        w = sum(
            1
            for p, o in rr
            for f in CHECK_FIELDS
            if f in p.truth and f in o.profile and not same(f, o.profile[f], p.truth[f], p.truth.get("_start_now", False))
        )
        by[lg] = {
            "candidates": len(os_),
            "completion_rate": _rate(sum(o.completed for o in os_), len(os_)),
            "median_replies": statistics.median([o.replies for o in os_ if o.completed]) if rr else None,
            "field_accuracy_when_present": _rate(r, r + w),
        }
    report["by_language"] = by
    handed = sum(1 for o in ast if o.stage == "handed_over")
    report["assistant"]["handed_over"] = handed
    report["currency"] = currency
    report["assistant"]["read_back_corrections"] = sum(o.corrections for o in ast)
    return report


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def markdown(r: dict[str, Any]) -> str:
    a, f, m = r["assistant"], r["form_bot"], r["matching"]
    s = r["assumptions"]
    lines = [
        "# Simulation report",
        "",
        f"{a['candidates']} simulated candidates (seed {r['seed']}), each with a hidden true profile, in eight languages. "
        "This is a simulation: the phrasings were written by the extractor's author, so it measures how the conversation runs and "
        "what reaches a recruiter, not how well unseen messages are read. Reading accuracy on blind-written messages is in `reports/heldout/`.",
        "",
        "Assumptions, the same for both flows: each further prompt is answered with a per-candidate probability "
        f"of {s['patience']}; a silent candidate answers a reminder with probability {s['revive']}; {_pct(s['consent'])} give consent; "
        f"reply delays {s['reply_delay']}; reminders after 20 h, 72 h and 168 h, inside quiet hours and the 24-hour window rules.",
        "",
        "## Assistant against a form bot",
        "",
        "| | Assistant | Form bot (reads perfectly) |",
        "|---|---:|---:|",
        f"| Reached a decision (hand-over, talent pool or no match) | {_pct(a['completion_rate'])} ({a['completed']}) | {_pct(f['completion_rate'])} ({f['completed']}) |",
        f"| Messages the candidate sent (median, completed) | {a['median_replies_when_completed']} | {f['median_replies_when_completed']} |",
        f"| Minutes to a decision (median) | {a['median_minutes_to_done']} | {f['median_minutes_to_done']} |",
        f"| Reminders, free-form / template | {a['reminders_free_form']} / {a['reminders_template']} | {f['reminders_free_form']} / {f['reminders_template']} |",
        f"| Messages from the business (free-form) | {a['service_messages']} | {f['service_messages']} |",
        f"| WhatsApp cost below 1,000 service messages a month ({r['currency']}) | {a['cost_small']:.2f} | {f['cost_small']:.2f} |",
        f"| WhatsApp cost at volume, every message charged ({r['currency']}) | {a['cost_at_volume']:.2f} | {f['cost_at_volume']:.2f} |",
        f"| … per candidate who reached a decision ({r['currency']}) | {a['cost_at_volume_per_decision']:.3f} | {f['cost_at_volume_per_decision']:.3f} |",
        "",
        f"The assistant handed {a['handed_over']} candidates to a recruiter. Candidates corrected the read-back {a['read_back_corrections']} times. "
        "Prices: Meta's German rates from 1 October 2026 (service messages free up to 1,000 a month per number, then charged at the utility rate).",
        "",
        "How assistant conversations ended: " + "; ".join(f"{k} {v}" for k, v in a["outcomes"].items()) + ".",
        "",
        "## What reaches a recruiter",
        "",
        f"{m['candidates_with_a_deserved_job']} candidates deserve at least one job (fit or near on their true profile).",
        "",
        "| | Assistant | Keyword forwarding |",
        "|---|---:|---:|",
        f"| Candidate-job pairs forwarded | {m['assistant']['forwarded']} | {m['keyword']['forwarded']} |",
        f"| Of those, deserved (precision) | {_pct(m['assistant']['precision'])} | {_pct(m['keyword']['precision'])} |",
        f"| Deserving candidates reached (recall) | {_pct(m['assistant']['recall'])} | {_pct(m['keyword']['recall'])} |",
        "",
        f"The assistant's verdict (fit or near) equals the verdict on the true profile for {_pct(m['assistant']['verdict_agrees_with_truth'])} "
        "of the pairs it forwarded. Keyword recall counts everyone who wrote; the assistant's recall also pays for every candidate who stopped answering.",
        "",
        "## Fields, completed conversations",
        "",
        f"Language detected right: {_pct(r['language_detected_right'])}. Field values right when present: {_pct(r['field_accuracy_when_present'])}.",
        "",
        "| Field | Right | Wrong | Not asked or missing | Accuracy when present |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, v in r["fields"].items():
        lines.append(f"| {k} | {v['right']} | {v['wrong']} | {v['not_asked_or_missing']} | {_pct(v['accuracy_when_present'])} |")
    lines += ["", "## By language", "", "| Language | Candidates | Completed | Median messages | Field accuracy |", "|---|---:|---:|---:|---:|"]
    for k, v in r["by_language"].items():
        lines.append(f"| {k} | {v['candidates']} | {_pct(v['completion_rate'])} | {v['median_replies']} | {_pct(v['field_accuracy_when_present'])} |")
    return "\n".join(lines) + "\n"
