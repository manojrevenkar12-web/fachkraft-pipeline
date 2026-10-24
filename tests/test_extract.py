"""The offline extractor on the shapes candidates write, in every supported language."""

from datetime import date

import pytest

from fkp.extract import RuleExtractor
from fkp.lang import detect

TODAY = date(2026, 10, 24)
X = RuleExtractor()


def read(text, asked=None, lang=None):
    r = X.read(text, lang or detect(text), TODAY, asked)
    return {f.field: f.value for f in r.facts}, r


@pytest.mark.parametrize(
    "text,lang",
    [
        ("Hallo, ich bin Elektriker, wohne in München", "de"),
        ("I'm a truck driver living in Hamburg", "en"),
        ("Merhaba, kaynakçıyım, Köln'de oturuyorum", "tr"),
        ("Jestem magazynierem, mieszkam w Dortmundzie", "pl"),
        ("Sunt instalator și locuiesc în Hamburg", "ro"),
        ("Я зварник, живу в Лейпцигу", "uk"),
        ("Я повар, живу в Мюнхене", "ru"),
        ("أنا نجار وأسكن في برلين", "ar"),
    ],
)
def test_language_detection_and_occupation_in_every_language(text, lang):
    assert detect(text) == lang
    v, _ = read(text)
    assert v.get("occupation"), text
    assert v.get("location"), text


def test_evidence_is_the_original_words():
    text = "Bin Kfz-Mechatroniker seit 2015, wohne 45127 Essen, Führerschein B"
    _, r = read(text)
    ev = {f.field: f.evidence(text) for f in r.facts}
    assert ev["occupation"] == "Kfz-Mechatroniker"
    assert ev["location"] == "45127"
    assert r.get("experience_years").value == 11


def test_licence_classes_with_context_cyrillic_lookalikes_and_implication():
    v, _ = read("Права категорії С і СЕ, код 95", lang="uk")
    assert v["licences"] == ["B", "C", "CE", "code95"]
    v, _ = read("Ich habe Deutsch C1", lang="de")
    assert "licences" not in v and v["german_level"] == "C1"
    v, _ = read("nur B", asked="licences", lang="de")
    assert v["licences"] == ["B"]


def test_age_is_never_read_as_experience():
    v, r = read("Ich bin 34 Jahre alt und Maler", lang="de")
    assert "experience_years" not in v and r.age_mentioned
    v, _ = read("Ich arbeite seit 12 Jahren als Maler", lang="de")
    assert v["experience_years"] == 12


def test_shifts_with_negation_and_short_words_only_in_context():
    v, _ = read("Frühschicht und Spätschicht gerne, aber keine Nachtschicht", lang="de")
    assert v["shifts"] == {"early": True, "late": True, "night": False}
    v, _ = read("Ich kann früh anfangen", lang="de")
    assert "shifts" not in v
    v, _ = read("früh und spät", asked="shifts", lang="de")
    assert v["shifts"] == {"early": True, "late": True}
    v, _ = read("her vardiya olur", lang="tr")
    assert all(v["shifts"].values())


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ab sofort", "2026-10-24"),
        ("ab 1.12.", "2026-12-01"),
        ("ab dem 15.03.2027", "2027-03-15"),
        ("in 2 Wochen", "2026-11-07"),
        ("od stycznia", "2027-01-01"),
        ("next month", "2026-11-01"),
        ("1. März", "2027-03-01"),
    ],
)
def test_start_dates(text, expected):
    v, _ = read(text, asked="start_date")
    assert v["start_date"] == expected


def test_recognition_and_foreign_qualification():
    v, _ = read("Pflegefachkraft aus den Philippinen, Anerkennung läuft", lang="de")
    assert (v["qualification"], v["recognition"]) == ("foreign", "in_progress")
    v, _ = read("Krankenschwester, noch keine Anerkennung", lang="de")
    assert v["recognition"] == "not_started"
    v, _ = read("ja", asked="recognition", lang="de")
    assert v["recognition"] == "recognised"


def test_german_level_words():
    assert read("Ich spreche kein Deutsch", lang="de")[0]["german_level"] == "none"
    assert read("almancam biraz, A2 civarı", lang="tr")[0]["german_level"] == "A2"
    assert read("fließend Deutsch", lang="de")[0]["german_level"] == "C1"


def test_intents():
    assert "opt_out" in read("STOP")[1].intents
    assert "opt_out" in read("видаліть мої дані", lang="uk")[1].intents
    assert "human" in read("Bitte anrufen", lang="de")[1].intents
    assert "yes" in read("Ja, passt", lang="de")[1].intents
    assert "yes" not in read("no tak", lang="pl")[1].intents or "no" not in read("no tak", lang="pl")[1].intents


def test_chef_is_a_boss_in_german():
    v, _ = read("Mein Chef sagt, ich bin ein guter Lagerist", lang="de")
    assert v["occupation"] == ["lagerlogistik"]


def test_money_is_not_a_postcode_and_food_is_not_a_town():
    v, _ = read("Ich möchte 35000 € brutto", lang="de")
    assert "location" not in v
    v, _ = read("Das Essen in der Kantine ist wichtig", lang="de")
    assert "location" not in v


@pytest.mark.parametrize(
    "text,lang,want",
    [
        ("nur Frühschicht", "de", {"early": True, "late": False, "night": False}),
        ("early shift only", "en", {"early": True, "late": False, "night": False}),
        ("sadece sabah vardiyası", "tr", {"early": True, "late": False, "night": False}),
        ("وردية صباحية فقط", "ar", {"early": True, "late": False, "night": False}),
        ("pierwsza i druga zmiana tak, bez nocek", "pl", {"early": True, "late": True, "night": False}),
        ("وردية صباحية ومسائية نعم، لا ليلي", "ar", {"early": True, "late": True, "night": False}),
    ],
)
def test_only_one_shift_refuses_the_others_and_coordinated_shifts(text, lang, want):
    got, _ = read(text, asked="shifts", lang=lang)
    assert got["shifts"] == want


def test_c1_belongs_to_the_closer_word():
    got, _ = read("permis categoria B, germană C1", lang="ro")
    assert got["licences"] == ["B"] and got["german_level"] == "C1"
    got, _ = read("Führerschein C1 und CE, Deutsch B1", lang="de")
    assert "C1" in got["licences"] and got["german_level"] == "B1"


def test_arabic_clitics_and_article_do_not_hide_words():
    got, _ = read("أنا سباك وأسكن في ميونخ", lang="ar")
    assert got["occupation"] == ["anlagenmechaniker_shk"] and got["location"]["plz"] == "80331"
    got, _ = read("الوردية الليلية لا", asked="shifts", lang="ar")
    assert got["shifts"] == {"night": False}
