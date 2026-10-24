"""Whole conversations through the agent, without a database."""

from datetime import timedelta

import pytest

from fkp.dialogue import Agent, Conversation, Inbound

from .conftest import T0


class Chat:
    def __init__(self, jobs, name="Mehmet Kaya"):
        self.agent = Agent(jobs)
        self.conv = Conversation(id="c", phone="491700000000")
        self.t = T0
        self.name = name
        self.events = []
        self.out = []

    def send(self, text="", button=""):
        self.t += timedelta(minutes=3)
        r = self.agent.handle(
            self.conv,
            Inbound(id=str(self.t.timestamp()), at=self.t, kind="button" if button else "text", text=text, button_id=button, profile_name=self.name),
        )
        self.events += r.events
        self.out = r.outgoing
        return r

    @property
    def last(self):
        return self.out[-1] if self.out else None

    def types(self):
        return [e["type"] for e in self.events]


def test_consent_comes_first_and_nothing_is_read_before_it(demo_jobs):
    c = Chat(demo_jobs)
    r = c.send("Hallo, ich bin Elektriker aus München und kann sofort anfangen")
    assert r.outgoing[0].purpose == "intro" and "KI" in r.outgoing[0].body and [b[0] for b in r.outgoing[0].buttons] == ["consent_yes", "consent_no"]
    assert c.conv.profile == {} and c.conv.stage == "awaiting_consent"
    c.send("Wie bitte?")
    assert c.last.purpose == "consent_again" and c.conv.profile == {}
    c.send(button="consent_yes")
    # the first message is read now, so its facts are not asked again
    assert {"occupation", "location", "start_date"} <= set(c.conv.profile)
    assert c.last.purpose.startswith("question:") and c.last.purpose not in ("question:occupation", "question:location", "question:start_date")


def test_declining_keeps_nothing(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hallo, ich bin Lagerist in Dortmund")
    c.send(button="consent_no")
    assert c.conv.stage == "declined" and c.conv.pending_text == "" and c.conv.profile == {}


def test_targeted_questions_follow_the_job(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Ich interessiere mich für J-PFK-BER")
    c.send(button="consent_yes")
    c.send("Ich bin Krankenschwester aus der Türkei, wohne in 10247 Berlin, ab Januar")
    asked = []
    for answer in ["Anerkennung läuft", "früh und spät, Wochenende ok", "Deutsch B2", "4 Jahre"]:
        asked.append(c.last.purpose)
        c.send(answer)
    assert asked == ["question:recognition", "question:shifts", "question:german_level", "question:experience_years"]
    assert c.last.purpose == "confirm"


def test_full_conversation_hands_over_with_a_reply_date(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hallo, J-LKW-LEJ: LKW-Fahrer mit CE und Code 95, wohne in 04315 Leipzig")
    c.send(button="consent_yes")
    for a in ["ab 1.12.", "früh und spät, keine Nacht", "8 Jahre"]:
        c.send(a)
    assert c.last.purpose == "confirm" and "Code 95" in c.last.body
    c.send(button="confirm_yes")
    assert c.last.purpose == "question:email"
    c.send("mehmet.kaya@mail.example")
    assert c.conv.stage == "handed_over" and c.last.purpose == "matched" and "27.10." in c.last.body
    handover = next(e for e in c.events if e["type"] == "handover")
    assert handover["jobs"] == [{"job_id": "J-LKW-LEJ", "verdict": "fit"}]


def test_corrections_override_and_licences_merge(demo_jobs):
    c = Chat(demo_jobs)
    c.send("J-LKW-LEJ")
    c.send(button="consent_yes")
    c.send("Berufskraftfahrer mit Führerschein C, wohne in Leipzig 04109, ab sofort")
    c.send("auch CE und Code 95")
    assert set(c.conv.profile["licences"].value) >= {"C", "CE", "code95"}
    while c.last.purpose != "confirm":
        c.send("früh" if "shifts" in c.last.purpose else "5 Jahre")
    c.send(button="confirm_fix")
    assert c.conv.stage == "fixing"
    c.send("nein, ich wohne in 04315 Leipzig")
    assert c.conv.profile["location"].value["plz"] == "04315" and c.last.purpose == "confirm"


def test_stop_deletes_everything_in_any_language(demo_jobs):
    for word in ("STOP", "Stopp", "dur", "koniec", "стоп", "توقف"):
        c = Chat(demo_jobs)
        c.send("Hallo, Elektriker in München")
        c.send(button="consent_yes")
        c.send(word)
        assert c.conv.stage == "deleted" and c.conv.profile == {} and "deleted" in c.types(), word
        assert c.send("Noch eine Frage").outgoing == []


def test_human_hand_off_and_voice_messages(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hallo")
    c.send(button="consent_yes")
    r = c.agent.handle(c.conv, Inbound(id="v1", at=c.t + timedelta(minutes=1), kind="audio"))
    assert r.outgoing[0].purpose == "voice"
    c.send("Ich möchte lieber mit einem Menschen sprechen")
    assert c.conv.stage == "human" and c.last.purpose == "human"
    assert c.send("Hallo?").outgoing == []  # a recruiter answers now, not the bot


def test_no_fit_offers_the_talent_pool_with_a_separate_yes(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hello")
    c.send(button="consent_yes")
    c.send("I am a cook in Flensburg, available immediately")
    while c.last.purpose != "confirm":
        c.send({"question:shifts": "any shift", "question:german_level": "B1"}.get(c.last.purpose, "3 years"))
    c.send(button="confirm_yes")
    assert c.conv.stage == "pool_question"
    c.send(button="pool_yes")
    assert c.conv.stage == "pooled" and c.conv.pool_until


def test_question_budget_is_respected(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hallo")
    c.send(button="consent_yes")
    for _ in range(20):
        if c.last.purpose == "confirm":
            break
        c.send("hm")
    assert c.last.purpose == "confirm"
    assert c.conv.questions <= 2 * 7


@pytest.mark.parametrize("lang,first", [("tr", "Merhaba"), ("pl", "Dzień dobry, jestem"), ("ar", "مرحبا"), ("uk", "Привіт, я зварник")])
def test_replies_in_the_candidates_language(demo_jobs, lang, first):
    c = Chat(demo_jobs)
    c.send(first)
    assert c.conv.lang == lang
    assert c.last.body == c.agent.msgs[lang]["intro"].format(
        name=" Mehmet", company=c.agent.company, job_part="", retention_months=6, privacy_url=c.agent.st["privacy_url"]
    )


def test_reminders_respect_window_quiet_hours_and_cap(demo_jobs):
    c = Chat(demo_jobs)
    c.send("Hallo, Elektriker")
    c.send(button="consent_yes")
    assert c.last.purpose == "open_question"
    a = c.agent
    assert a.reminder(c.conv, c.t + timedelta(hours=10)) is None
    r1 = a.reminder(c.conv, c.t + timedelta(hours=23))  # due after 20 h, moved out of quiet hours to 08:00
    assert r1.kind == "text"  # still inside 24 hours: a normal message
    r2 = a.reminder(c.conv, c.t + timedelta(days=4))
    assert r2.kind == "template" and r2.template["category"] == "utility" and r2.template["language"] == "de"
    assert a.reminder(c.conv, c.t + timedelta(days=9)) is not None
    assert a.reminder(c.conv, c.t + timedelta(days=30)) is None  # three at most


def test_reminder_moves_out_of_quiet_hours(demo_jobs):
    from datetime import UTC, datetime

    from fkp import calendar

    c = Chat(demo_jobs)
    c.t = datetime(2026, 10, 30, 23, 0, tzinfo=UTC)  # Saturday 01:00 in Berlin
    c.send("Hallo, Elektriker")
    c.send(button="consent_yes")
    # due 20 h later = Saturday 21:06, inside quiet hours; Sunday is blocked: Monday 08:00
    assert c.agent.reminder(c.conv, datetime(2026, 10, 31, 21, 0, tzinfo=UTC)) is None
    assert c.agent.reminder(c.conv, datetime(2026, 11, 1, 12, 0, tzinfo=UTC)) is None
    r = c.agent.reminder(c.conv, datetime(2026, 11, 2, 7, 0, tzinfo=UTC))
    assert r is not None and r.kind == "template"  # 2 days later the window is closed: template only
    assert calendar.next_send_slot(datetime(2026, 10, 31, 20, 30, tzinfo=UTC)).astimezone(calendar.tz()).strftime("%a %H:%M") == "Mon 08:00"


def test_a_correction_replaces_a_list_instead_of_adding_to_it(demo_jobs):
    c = Chat(demo_jobs)
    c.send("J-LKW-LEJ")
    c.send(button="consent_yes")
    c.send("Berufskraftfahrer, Führerschein C1 und CE, wohne in 04109 Leipzig, ab sofort")
    while c.last.purpose != "confirm":
        c.send("früh und spät" if "shifts" in c.last.purpose else "Code 95" if "licences" in c.last.purpose else "5 Jahre")
    c.send("Führerschein CE und Code 95")  # the read-back said C1 as well; the candidate restates
    assert "C1" not in c.conv.profile["licences"].value and {"CE", "code95"} <= set(c.conv.profile["licences"].value)
    assert c.last.purpose == "confirm"
