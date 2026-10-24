"""The conversation: consent first, then as few questions as the next step needs.

`Agent.handle` takes a conversation and one inbound message and returns what to send and what
happened. It is pure (no database, no network, time passed in), so every path is testable and the
same code runs behind the WhatsApp webhook, the sandbox and the simulator.

Order of business in every conversation:

1. Say that this is an AI assistant (AI Act Art. 50), what the data is for and for how long, and
   ask for consent. Nothing is extracted before a yes. The first message is kept until then, so
   facts in it are not asked again.
2. One open question ("tell me about yourself"), because one free-text answer usually covers half
   the profile. Then targeted questions only for what the target job, or the candidate's
   occupation, actually needs: a nurse is asked about recognition, a driver about licences.
3. Read back what was understood and let the candidate correct it.
4. Match. Ask for name and email only now, and only if a job fits (the ATS needs them).
5. Hand over to the ATS with a promised reply date, or offer the talent pool, or delete.

"stop" in any language deletes everything at any point; "human" hands the conversation to a
recruiter.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, ClassVar

from . import calendar, config, lang, matching
from .extract import Reading, RuleExtractor
from .jobs import Job

STAGES = (
    "new",
    "awaiting_consent",
    "declined",
    "collecting",
    "confirming",
    "fixing",
    "handover_details",
    "pool_question",
    "handed_over",
    "pooled",
    "human",
    "deleted",
    "closed",
)
QUESTION_ORDER = (
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
)
DRIVING = {"berufskraftfahrer", "busfahrer", "lagerlogistik"}
_JOB_REF = re.compile(r"\b(J-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b")
_ONLY = ["nur", "only", "tylko", "doar", "sadece", "только", "тільки", "فقط"]


@dataclass
class FieldValue:
    value: Any
    evidence: str
    message_id: str
    source: str
    confidence: float
    at: str


@dataclass
class Inbound:
    id: str
    at: datetime
    kind: str = "text"  # text, button, audio, image, document
    text: str = ""
    button_id: str = ""
    profile_name: str = ""


@dataclass
class Outgoing:
    kind: str  # text, buttons, template
    body: str
    purpose: str
    buttons: list[tuple[str, str]] = field(default_factory=list)
    template: dict[str, Any] | None = None


@dataclass
class Conversation:
    id: str
    phone: str
    lang: str = "de"
    stage: str = "new"
    job_id: str | None = None
    wa_name: str = ""
    consent_at: str | None = None
    pending_text: str = ""
    pending_message_id: str = ""
    asked: str | None = None
    asked_counts: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    questions: int = 0
    confirm_rounds: int = 0
    profile: dict[str, FieldValue] = field(default_factory=dict)
    last_inbound_at: str | None = None
    last_outbound_at: str | None = None
    reminders_sent: int = 0
    matches: list[dict[str, Any]] = field(default_factory=list)
    pool_until: str | None = None
    handed_over_at: str | None = None
    flags: list[str] = field(default_factory=list)

    def values(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.profile.items()}

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Conversation:
        d = dict(d)
        d["profile"] = {k: FieldValue(**v) for k, v in (d.get("profile") or {}).items()}
        return cls(**d)


@dataclass
class Result:
    outgoing: list[Outgoing] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(self, jobs: list[Job], extractor: Any = None, company: str | None = None) -> None:
        self.jobs = {j.id: j for j in jobs}
        self.extractor = extractor or RuleExtractor()
        self.st = config.settings()
        self.msgs = config.messages()
        self.company = company or self.st["company"]

    # -- entry point ---------------------------------------------------------------------------

    def handle(self, conv: Conversation, msg: Inbound) -> Result:
        res = Result()
        now = msg.at
        conv.last_inbound_at = now.isoformat()
        conv.reminders_sent = 0
        if msg.profile_name and not conv.wa_name:
            conv.wa_name = msg.profile_name
        text = msg.text or ""
        if msg.kind == "text" and text.strip():
            conv.lang = lang.detect(text, default=conv.lang)
        if conv.stage in ("deleted", "declined", "closed") and text.strip().lower() in ("start", "/start", "hallo", "hi", "hello"):
            fresh = Conversation(id=conv.id, phone=conv.phone, lang=conv.lang, wa_name=conv.wa_name)
            conv.__dict__.update(fresh.__dict__)
        expect = frozenset(f for f in conv.asked_counts if f not in conv.profile)
        reading = self.extractor.read(text, conv.lang, now.date(), conv.asked, expect) if text else Reading()

        if "opt_out" in reading.intents and conv.stage not in ("deleted",):
            return self._delete(conv, res, "opt_out", now)
        if conv.stage in ("deleted", "declined", "closed"):
            return res
        if "human" in reading.intents and conv.stage not in ("human",):
            conv.stage = "human"
            res.events.append({"type": "human_requested"})
            self._say(conv, res, now, "text", self._t(conv, "human", deadline=self._deadline(conv, now)), "human")
            return res
        if conv.stage in ("human", "handed_over", "pooled"):
            res.events.append({"type": "message_for_recruiter", "message_id": msg.id})
            return res
        if msg.kind == "audio" and not text:
            self._say(conv, res, now, "text", self._t(conv, "voice"), "voice")
            return res
        if msg.kind in ("image", "document"):
            res.events.append({"type": "document_received", "message_id": msg.id})
            if not text:
                return res

        handler = getattr(self, f"_on_{conv.stage}")
        handler(conv, msg, reading, res)
        return res

    # -- stages --------------------------------------------------------------------------------

    def _on_new(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        m = _JOB_REF.search(msg.text or "")
        if m and m.group(1) in self.jobs:
            conv.job_id = m.group(1)
        conv.pending_text = msg.text or ""
        conv.pending_message_id = msg.id
        name = f" {conv.wa_name.split()[0]}" if conv.wa_name.strip() else ""
        job = self.jobs.get(conv.job_id or "")
        job_part = self._t(conv, "job_part", job=job.title) if job else ""
        body = self._t(
            conv,
            "intro",
            name=name,
            company=self.company,
            job_part=job_part,
            retention_months=self.st["retention"]["rejected_months"],
            privacy_url=self.st["privacy_url"],
        )
        conv.stage = "awaiting_consent"
        self._say(
            conv, res, msg.at, "buttons", body, "intro", [("consent_yes", self._t(conv, "consent_yes")), ("consent_no", self._t(conv, "consent_no"))]
        )

    def _on_awaiting_consent(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        if msg.button_id == "consent_yes" or ("yes" in reading.intents and "no" not in reading.intents):
            conv.consent_at = msg.at.isoformat()
            conv.stage = "collecting"
            res.events.append({"type": "consent_given", "at": conv.consent_at})
            pending, conv.pending_text = conv.pending_text, ""
            got = 0
            if pending:
                got = self._absorb(conv, self.extractor.read(pending, conv.lang, msg.at.date(), None), pending, conv.pending_message_id, msg.at)
            if got >= 2:
                self._next(conv, msg.at, res)
            else:
                conv.asked = None
                self._say(conv, res, msg.at, "text", self._t(conv, "open_question"), "open_question")
            return
        if msg.button_id == "consent_no" or "no" in reading.intents:
            conv.stage = "declined"
            conv.pending_text = ""
            res.events.append({"type": "consent_declined"})
            self._say(conv, res, msg.at, "text", self._t(conv, "consent_declined"), "declined")
            return
        # anything else: ask again, with the buttons; nothing is read before a yes
        self._say(
            conv,
            res,
            msg.at,
            "buttons",
            self._t(conv, "not_understood", question=self._t(conv, "consent_question")),
            "consent_again",
            [("consent_yes", self._t(conv, "consent_yes")), ("consent_no", self._t(conv, "consent_no"))],
        )

    def _on_collecting(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        asked = conv.asked
        got = self._absorb(conv, reading, msg.text, msg.id, msg.at)
        if reading.health_mentioned:
            res.events.append({"type": "health_redacted", "message_id": msg.id})
        conv.skipped = [f for f in conv.skipped if f not in conv.profile]
        if asked and asked not in conv.profile:
            if conv.asked_counts.get(asked, 0) < 2:
                # answered something else: ask again; answered nothing we understood: say so
                self._ask(conv, res, msg.at, asked, retry=not got)
                return
            conv.skipped.append(asked)
        self._next(conv, msg.at, res)

    def _on_confirming(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        if msg.button_id == "confirm_yes" or ("yes" in reading.intents and "no" not in reading.intents):
            res.events.append({"type": "profile_confirmed"})
            self._finalize(conv, msg.at, res)
            return
        got = self._absorb(conv, reading, msg.text, msg.id, msg.at, override=True) if msg.text else 0
        if got:
            conv.confirm_rounds += 1
            self._confirm(conv, msg.at, res)
            return
        conv.stage = "fixing"
        conv.asked = None
        self._say(conv, res, msg.at, "text", self._t(conv, "fix_prompt"), "fix_prompt")

    def _on_fixing(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        got = self._absorb(conv, reading, msg.text, msg.id, msg.at, override=True)
        conv.confirm_rounds += 1
        if not got and conv.confirm_rounds >= 2:
            conv.stage = "human"
            res.events.append({"type": "human_requested", "reason": "correction not understood"})
            self._say(conv, res, msg.at, "text", self._t(conv, "human", deadline=self._deadline(conv, msg.at)), "human")
            return
        self._confirm(conv, msg.at, res)

    def _on_handover_details(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        self._absorb(conv, reading, msg.text, msg.id, msg.at)
        missing = self._handover_missing(conv)
        if missing:
            f = missing[0]
            if conv.asked_counts.get(f, 0) >= 2:
                conv.skipped.append(f)
            else:
                self._ask(conv, res, msg.at, f, retry=conv.asked == f)
                return
        self._handover(conv, msg.at, res)

    def _on_pool_question(self, conv: Conversation, msg: Inbound, reading: Reading, res: Result) -> None:
        if msg.button_id == "pool_yes" or ("yes" in reading.intents and "no" not in reading.intents):
            until = msg.at + timedelta(days=30 * self.st["retention"]["talent_pool_months"])
            conv.pool_until = until.isoformat()
            conv.stage = "pooled"
            res.events.append({"type": "pooled", "until": conv.pool_until})
            self._say(conv, res, msg.at, "text", self._t(conv, "pool_saved"), "pool_saved")
        elif msg.button_id == "pool_no" or "no" in reading.intents:
            self._delete(conv, res, "pool_declined", msg.at)
        else:
            self._pool_question(conv, msg.at, res)

    # -- steps ---------------------------------------------------------------------------------

    def _absorb(self, conv: Conversation, reading: Reading, text: str, message_id: str, at: datetime, override: bool = False) -> int:
        """Merge what a message says into the profile; returns how many fields changed."""
        changed = 0
        folded = (text or "").lower()
        only = any(re.search(rf"(?<!\w){w}(?!\w)", folded) for w in _ONLY)
        for f in reading.facts:
            old = conv.profile.get(f.field)
            value = f.value
            if old is not None and not override and f.field != conv.asked and f.confidence + 0.05 < old.confidence:
                continue
            if old is not None and not only:
                # a correction states the whole list again; shifts are corrected one at a time
                if f.field in ("licences", "occupation", "employment") and isinstance(old.value, list) and not override:
                    value = list(dict.fromkeys([*old.value, *value])) if f.field != "licences" else sorted(set(old.value) | set(value))
                elif f.field == "shifts" and isinstance(old.value, dict):
                    value = {**old.value, **value}
            if old is not None and old.value == value:
                continue
            conv.profile[f.field] = FieldValue(
                value, f.evidence(text), message_id, getattr(self.extractor, "name", "rules"), f.confidence, at.isoformat()
            )
            changed += 1
        return changed

    def required(self, conv: Conversation) -> list[str]:
        v = conv.values()
        job = self.jobs.get(conv.job_id or "")
        need = ["occupation", "location", "start_date"]
        occs = v.get("occupation") or ([job.occupation] if job else [])
        regulated = any(config.occupations()[o].get("regulated") for o in occs) or bool(job and job.needs_recognition)
        if regulated:
            need.append("qualification")
            if v.get("qualification") in ("foreign", "trained"):
                need.append("recognition")
        if (job and job.must.get("licences")) or (not job and set(occs) & DRIVING):
            need.append("licences")
        if job is None or job.shifts:
            need.append("shifts")
        if job is None or job.german_min:
            need.append("german_level")
        need.append("experience_years")
        return [f for f in QUESTION_ORDER if f in need]

    def _next(self, conv: Conversation, at: datetime, res: Result) -> None:
        missing = [f for f in self.required(conv) if f not in conv.profile and f not in conv.skipped]
        if missing and conv.questions < self.st["conversation"]["max_questions"]:
            self._ask(conv, res, at, missing[0])
            return
        self._confirm(conv, at, res)

    def _ask(self, conv: Conversation, res: Result, at: datetime, f: str, retry: bool = False) -> None:
        conv.asked = f
        conv.asked_counts[f] = conv.asked_counts.get(f, 0) + 1
        conv.questions += 1
        q = self._t(conv, "ask", key=f)
        body = self._t(conv, "not_understood", question=q) if retry else q
        res.events.append({"type": "question", "field": f, "retry": retry})
        self._say(conv, res, at, "text", body, f"question:{f}")

    def _confirm(self, conv: Conversation, at: datetime, res: Result) -> None:
        conv.stage = "confirming"
        conv.asked = None
        self._say(
            conv,
            res,
            at,
            "buttons",
            self._t(conv, "confirm", summary=self.summary(conv)),
            "confirm",
            [("confirm_yes", self._t(conv, "confirm_yes")), ("confirm_fix", self._t(conv, "confirm_fix"))],
        )

    def _finalize(self, conv: Conversation, at: datetime, res: Result) -> None:
        jobs = list(self.jobs.values())
        ranked = matching.rank(jobs, conv.values(), at.date())
        conv.matches = [m.to_dict() for m in ranked]
        # "unknown" left after the questions (the candidate skipped one) goes to a recruiter as a
        # near match; a clear "no" does not
        good = [m for m in ranked if m.verdict in ("fit", "near", "unknown")]
        for m in good:
            if m.verdict == "unknown":
                m.verdict = "near"
        target = next((m for m in good if m.job_id == conv.job_id), None)
        chosen = [target] if target else good[:2]
        res.events.append({"type": "matched", "matches": [m.to_dict() for m in chosen]})
        if not chosen:
            self._pool_question(conv, at, res)
            return
        conv.flags = [f for f in conv.flags if not f.startswith("job:")] + [f"job:{m.job_id}:{m.verdict}" for m in chosen]
        if self._handover_missing(conv):
            conv.stage = "handover_details"
            self._ask(conv, res, at, self._handover_missing(conv)[0])
            return
        self._handover(conv, at, res)

    def _handover_missing(self, conv: Conversation) -> list[str]:
        out = []
        for f in self.st["conversation"]["fields_for_handover"]:
            if f in conv.profile or f in conv.skipped:
                continue
            if f == "full_name" and len(conv.wa_name.split()) >= 2:
                continue
            out.append(f)
        return out

    def _handover(self, conv: Conversation, at: datetime, res: Result) -> None:
        conv.stage = "handed_over"
        conv.handed_over_at = at.isoformat()
        conv.asked = None
        chosen = [f.split(":") for f in conv.flags if f.startswith("job:")]
        titles = ", ".join(self.jobs[j].title for _, j, _ in chosen if j in self.jobs)
        near = [j for _, j, v in chosen if v == "near"]
        res.events.append({"type": "handover", "jobs": [{"job_id": j, "verdict": v} for _, j, v in chosen]})
        deadline = self._deadline(conv, at)
        if near and len(near) == len(chosen):
            gaps = []
            for m in conv.matches:
                if m["job_id"] in near:
                    gaps += [self._gap_label(conv, c) for c in m["checks"] if c["status"] in ("fixable", "fail", "unknown")]
            self._say(
                conv, res, at, "text", self._t(conv, "near_miss", jobs=titles, gaps="; ".join(dict.fromkeys(gaps)), deadline=deadline), "near_miss"
            )
        else:
            self._say(conv, res, at, "text", self._t(conv, "matched", jobs=titles, deadline=deadline), "matched")

    _CHECK_FIELD: ClassVar[dict[str, str]] = {
        "recognition": "recognition",
        "licences": "licences",
        "start": "start_date",
        "german": "german_level",
        "commute": "location",
        "shifts": "shifts",
        "occupation": "occupation",
        "employment": "employment",
    }

    def _gap_label(self, conv: Conversation, check: dict[str, Any]) -> str:
        """A gap in the candidate's language: the field's label, plus the missing licences."""
        labels = (self.msgs.get(conv.lang) or self.msgs["de"])["labels"]
        label = str(labels.get(self._CHECK_FIELD.get(check["name"], check["name"]), check["name"]))
        if check["name"] == "licences" and "missing" in check["detail"]:
            items = check["detail"].split("missing", 1)[1].strip()
            values = (self.msgs.get(conv.lang) or self.msgs["de"])["values"]
            return f"{label}: " + ", ".join(_licence_label(x.strip(), values) for x in items.split(","))
        return label

    def _pool_question(self, conv: Conversation, at: datetime, res: Result) -> None:
        conv.stage = "pool_question"
        self._say(
            conv,
            res,
            at,
            "buttons",
            self._t(conv, "no_match", retention_months=self.st["retention"]["talent_pool_months"]),
            "pool_question",
            [("pool_yes", self._t(conv, "pool_yes")), ("pool_no", self._t(conv, "pool_no"))],
        )

    def _delete(self, conv: Conversation, res: Result, reason: str, at: datetime) -> Result:
        """Erase the profile and history (GDPR Art. 17); keep only that this number said stop."""
        fresh = Conversation(id=conv.id, phone=conv.phone, lang=conv.lang, stage="deleted", last_inbound_at=at.isoformat())
        conv.__dict__.update(fresh.__dict__)
        res.events.append({"type": "deleted", "reason": reason})
        self._say(conv, res, at, "text", self._t(conv, "deleted"), "deleted")
        return res

    # -- reminders -----------------------------------------------------------------------------

    def reminder(self, conv: Conversation, now: datetime) -> Outgoing | None:
        """What to send when a candidate went quiet; None if nothing is due. Inside the 24-hour
        window a normal message; outside it only the approved utility template."""
        if conv.stage not in ("collecting", "confirming", "handover_details", "fixing") or not conv.last_inbound_at:
            return None
        f = self.st["followups"]
        if conv.reminders_sent >= f["max_reminders"]:
            return None
        last = datetime.fromisoformat(conv.last_outbound_at or conv.last_inbound_at)
        due = last + timedelta(hours=f["schedule_hours"][conv.reminders_sent])
        due = calendar.next_send_slot(due)
        if now < due:
            return None
        missing = self._missing_labels(conv)
        window = datetime.fromisoformat(conv.last_inbound_at) + timedelta(hours=self.st["whatsapp"]["window_hours"])
        conv.reminders_sent += 1
        if now < window:
            if conv.asked:
                question = self._t(conv, "ask", key=conv.asked)
            elif conv.stage == "collecting":
                question = self._t(conv, "open_question")
            else:
                question = self._t(conv, "confirm", summary=self.summary(conv))
            return Outgoing("text", question, f"reminder:{conv.reminders_sent}")
        tpl = self.st["whatsapp"]["templates"]["reminder"]
        params = {"company": self.company, "missing": missing}
        body = self._t(conv, "reminder", **params)
        return Outgoing(
            "template",
            body,
            f"reminder:{conv.reminders_sent}",
            template={"name": tpl["name"], "category": tpl["category"], "language": conv.lang, "params": [params[p] for p in tpl["params"]]},
        )

    def _missing_labels(self, conv: Conversation) -> str:
        labels = (self.msgs.get(conv.lang) or self.msgs["de"])["labels"]
        if conv.stage == "confirming":
            return str(labels["confirmation"])
        fields = [conv.asked] if conv.asked else [f for f in self.required(conv) if f not in conv.profile]
        return ", ".join(labels.get(f, f) for f in fields if f) or str(labels["confirmation"])

    # -- texts ---------------------------------------------------------------------------------

    def _t(self, conv: Conversation, msg_key: str, **kw: Any) -> str:
        m = self.msgs.get(conv.lang) or self.msgs["de"]
        if msg_key == "ask":
            return str(m["ask"][kw["key"]])
        return str(m[msg_key]).format(**kw) if kw else str(m[msg_key])

    def _deadline(self, conv: Conversation, at: datetime) -> str:
        d = calendar.add_business_days(at.astimezone(calendar.tz()).date(), self.st["conversation"]["recruiter_reply_business_days"])
        return d.strftime("%d.%m.%Y")

    def summary(self, conv: Conversation) -> str:
        m = self.msgs.get(conv.lang) or self.msgs["de"]
        L, V = m["labels"], m["values"]
        occ = config.occupations()
        lines = []
        for f in (*QUESTION_ORDER, "commute_km", "email", "full_name"):
            if f not in conv.profile:
                continue
            v = conv.profile[f].value
            if f == "occupation":
                s = ", ".join(occ[o]["label"].get(conv.lang, occ[o]["label"]["de"]) for o in v)
            elif f in ("qualification", "recognition"):
                s = V.get(v, v)
            elif f == "licences":
                s = ", ".join(_licence_label(x, V) for x in v) or V["none"]
            elif f == "location":
                s = f"{v.get('plz', '')} {v.get('place', '')}".strip()
            elif f == "shifts":
                ok = [V[k] for k in ("early", "late", "night", "weekend") if v.get(k)]
                no = [V[k] for k in ("early", "late", "night", "weekend") if v.get(k) is False]
                s = ", ".join(ok) + (f" ({V['no']}: {', '.join(no)})" if no else "") if ok else f"{V['no']}: {', '.join(no)}"
            elif f == "start_date":
                d = date.fromisoformat(v)
                s = V["immediately"] if d <= datetime.fromisoformat(conv.profile[f].at).date() else d.strftime("%d.%m.%Y")
            elif f == "experience_years":
                s = f"{v} {V['years']}"
            elif f == "employment":
                s = ", ".join(V.get(x, x) for x in v)
            elif f == "commute_km":
                s = f"{v} km"
                lines.append(f"• {L['commute']}: {s}")
                continue
            else:
                s = str(v)
            lines.append(f"• {L.get(f, f)}: {s}")
        return "\n".join(lines)

    def _say(
        self, conv: Conversation, res: Result, at: datetime, kind: str, body: str, purpose: str, buttons: list[tuple[str, str]] | None = None
    ) -> None:
        conv.last_outbound_at = at.isoformat()
        res.outgoing.append(Outgoing(kind, body, purpose, buttons or []))


def _licence_label(x: str, values: dict[str, Any]) -> str:
    return str(values.get(x) or {"code95": "Code 95", "adr": "ADR"}.get(x, x))
