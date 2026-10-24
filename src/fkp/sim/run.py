"""Play one simulated candidate through the assistant, or through a fixed form bot.

Both get the same candidate, the same patience (the chance of answering each further prompt), the
same reply delays and the same reminder schedule; a silent candidate comes back after a reminder
with probability `revive`. The form bot is given every advantage: its answers are taken as
perfectly structured, so it never misreads anything. What differs is how many prompts each needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .. import config, matching
from ..dialogue import Agent, Conversation, Inbound, Outgoing
from ..jobs import Job
from .personas import Persona, T, first_message, open_answer, phrase

TERMINAL = {"matched", "near_miss", "deleted", "human", "pool_saved", "consent_declined"}
FORM_FIELDS = [
    "occupation",
    "location",
    "qualification",
    "recognition",
    "licences",
    "start_date",
    "shifts",
    "german_level",
    "experience_years",
    "employment",
    "full_name",
    "email",
]


@dataclass
class Assumptions:
    revive: float = 0.30  # a silent candidate answers a reminder
    consent: float = 0.96
    notices_error: float = 0.8  # a candidate spots a wrong value in the read-back
    pool_yes: float = 0.6
    max_days: int = 9


@dataclass
class Outcome:
    persona: str
    lang: str
    flow: str
    stage: str
    completed: bool
    replies: int  # messages the candidate had to send
    prompts: int
    minutes_to_done: float | None
    sent: int = 0  # free-form messages from the business (service messages)
    reminders_text: int = 0
    reminders_template: int = 0
    detected_lang: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    handed: list[tuple[str, str]] = field(default_factory=list)  # (job, verdict)
    corrections: int = 0


def _reply_delay(p: Persona) -> timedelta:
    r = p.rng.random()
    if r < 0.8:
        return timedelta(minutes=p.rng.randint(1, 6))
    if r < 0.95:
        return timedelta(hours=p.rng.uniform(1, 6))
    return timedelta(hours=p.rng.uniform(10, 18))


def same(fieldname: str, got: Any, truth: Any, start_now: bool = False) -> bool:
    """Is an extracted value the true one? Shifts compare on what the candidate actually said;
    "immediately" is right as the date it was said on (a reminder may have come days later)."""
    if fieldname == "start_date" and start_now:
        return isinstance(got, str) and abs((date.fromisoformat(got) - date.fromisoformat(truth)).days) <= 10
    if fieldname == "occupation":
        return set(truth) <= set(got or [])
    if fieldname == "location":
        return isinstance(got, dict) and (
            got.get("plz") == truth["plz"]
            or matching.geo.km(matching.geo.Place("", "", got["lat"], got["lon"]), matching.geo.Place("", "", truth["lat"], truth["lon"])) < 15
        )
    if fieldname == "licences":
        return set(got or []) == set(truth)
    if fieldname == "shifts":
        return isinstance(got, dict) and all(got.get(k, None) == v for k, v in truth.items() if k != "weekend")
    if fieldname == "qualification":
        return got == truth or (got == "trained" and truth in ("foreign", "domestic"))
    return bool(got == truth)


def _answer(p: Persona, out: Outgoing, conv: Conversation, today: date, a: Assumptions) -> tuple[str, str]:
    """(text, button) the persona sends in response to the bot's last prompt."""
    purpose = out.purpose
    if purpose in ("intro", "consent_again"):
        return ("", "consent_yes") if p.rng.random() < a.consent else ("", "consent_no")
    if purpose == "open_question":
        return open_answer(p, today), ""
    if purpose.startswith("question:"):
        f = purpose.split(":", 1)[1]
        if f in ("german_level", "experience_years") and p.rng.random() < 0.04:
            return T[p.lang]["dunno"], ""
        return phrase(p, f, today), ""
    if purpose in ("confirm", "fix_prompt"):
        wrong = [
            f
            for f in p.truth
            if f in conv.profile and f not in ("email",) and not same(f, conv.profile[f].value, p.truth[f], p.truth.get("_start_now", False))
        ]
        if wrong and p.rng.random() < a.notices_error:
            return phrase(p, wrong[0], today), ""
        if purpose == "fix_prompt":
            return phrase(p, "occupation", today), ""
        return "", "confirm_yes"
    if purpose == "pool_question":
        return ("", "pool_yes") if p.rng.random() < a.pool_yes else ("", "pool_no")
    return phrase(p, "occupation", today), ""


def assistant(p: Persona, jobs: list[Job], start: datetime, a: Assumptions, extractor: Any = None) -> Outcome:
    agent = Agent(jobs, extractor)
    conv = Conversation(id=p.id, phone=f"+49151{int(p.id[1:]):07d}")
    today = start.date()
    now = start
    n = 0
    last: Outgoing | None = None
    out = Outcome(p.id, p.lang, "assistant", "new", False, 0, 0, None)
    pending_text, pending_button = first_message(p, today), ""
    corrections = 0
    decided = False  # reached a match decision (hand-over, or the talent-pool question)
    while True:
        n += 1
        msg = Inbound(
            id=f"{p.id}-{n}",
            at=now,
            kind="button" if pending_button else "text",
            text=pending_text,
            button_id=pending_button,
            profile_name=p.full_name,
        )
        if last and last.purpose in ("confirm", "fix_prompt") and pending_text:
            corrections += 1
        res = agent.handle(conv, msg)
        out.replies += 1
        if not decided and any(e["type"] == "matched" for e in res.events):
            decided, out.profile = True, conv.values()  # before a "no" to the talent pool erases it
        if not res.outgoing:
            break
        last = res.outgoing[-1]
        out.prompts += 1
        out.sent += len(res.outgoing)
        conv.last_outbound_at = now.isoformat()
        if last.purpose in TERMINAL or conv.stage in ("handed_over", "pooled", "deleted", "declined", "human"):
            break
        # will the candidate answer this prompt?
        if p.rng.random() > p.patience:
            revived = False
            t = now
            while t < start + timedelta(days=a.max_days):
                t += timedelta(hours=1)
                r = agent.reminder(conv, t)
                if r is None:
                    continue
                conv.last_outbound_at = t.isoformat()
                if r.kind == "template":
                    out.reminders_template += 1
                else:
                    out.reminders_text += 1
                if p.rng.random() < a.revive:
                    revived, now = True, t + timedelta(minutes=p.rng.randint(2, 90))
                    break
            if not revived:
                break
        else:
            now = now + _reply_delay(p)
        pending_text, pending_button = _answer(p, last, conv, today, a)
    out.stage = conv.stage
    out.completed = decided
    out.minutes_to_done = (now - start).total_seconds() / 60 if out.completed else None
    out.detected_lang = conv.lang
    out.profile = out.profile or conv.values()
    out.handed = [(f.split(":")[1], f.split(":")[2]) for f in conv.flags if f.startswith("job:")] if conv.stage == "handed_over" else []
    out.corrections = corrections
    return out


def form_bot(p: Persona, start: datetime, a: Assumptions) -> Outcome:
    """A fixed questionnaire: consent, then every field one by one. Answers are taken as perfect."""
    out = Outcome(p.id, p.lang, "form", "new", False, 0, 0, None)
    now = start
    prompts = ["consent", *FORM_FIELDS, "submit"]
    last_inbound = start
    sent_reminders = 0
    st = config.settings()
    for i, step in enumerate(prompts):
        out.prompts += 1
        if step == "consent" and p.rng.random() >= a.consent:
            out.stage = "declined"
            out.sent = out.prompts
            return out
        if i and p.rng.random() > p.patience:
            revived = False
            for hours in st["followups"]["schedule_hours"][: st["followups"]["max_reminders"]]:
                t = now + timedelta(hours=hours)
                if t - last_inbound < timedelta(hours=st["whatsapp"]["window_hours"]):
                    out.reminders_text += 1
                else:
                    out.reminders_template += 1
                sent_reminders += 1
                if p.rng.random() < a.revive:
                    now, revived = t, True
                    break
            if not revived:
                out.stage = f"abandoned_at:{step}"
                out.sent = out.prompts
                return out
        now = now + _reply_delay(p)
        last_inbound = now
        out.replies += 1
    out.sent = out.prompts + 1  # every prompt, plus the closing message
    out.stage = "submitted"
    out.completed = True
    out.minutes_to_done = (now - start).total_seconds() / 60
    out.profile = {k: v for k, v in p.truth.items() if k != "email"}
    return out


def truth_matches(p: Persona, jobs: list[Job], today: date) -> dict[str, str]:
    return {m.job_id: m.verdict for m in matching.rank(jobs, p.truth, today)}


def keyword_forward(p: Persona, jobs: list[Job]) -> list[str]:
    """What a job-board keyword filter forwards: same occupation title, home within the radius."""
    home = matching.geo.Place("", "", p.truth["location"]["lat"], p.truth["location"]["lon"])
    return [j.id for j in jobs if j.open and j.occupation in p.truth["occupation"] and matching.geo.km(home, j.place) <= j.radius_km]
