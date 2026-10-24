import pytest

from fkp import jobs


def lint(title, text="", german=None):
    return {i.rule: i for i in jobs.check_agg({"title": title, "text": text, "german_level": german})}


def test_demo_jobs_are_clean(demo_jobs):
    for j in demo_jobs:
        assert [i.rule for i in jobs.check_agg(j)] == [], j.id


@pytest.mark.parametrize(
    "text,rule",
    [
        ("Deutsch als Muttersprache erforderlich", "origin-native-language"),
        ("Native speaker of German", "origin-native-language"),
        ("Wir sind ein junges Team", "age"),
        ("Bewerber bis 35 Jahre", "age"),
        ("Bitte mit Foto bewerben", "photo"),
        ("deutsche Staatsangehörigkeit", "origin-nationality"),
        ("keine Kinder", "family"),
    ],
)
def test_discriminating_wording_is_found(text, rule):
    assert rule in lint("Lagerist (m/w/d)", text)


def test_inclusive_statements_are_not_flagged():
    issues = lint("Lagerist (m/w/d)", "Wir freuen uns über Bewerbungen unabhängig von Herkunft, Religion, Alter und Geschlecht.")
    assert issues == {}


def test_title_needs_all_genders_and_german_needs_a_reason():
    assert "gender-title" in lint("Lagerist")
    for ok in ("Lagerist (m/w/d)", "Lagerist*in", "Pflegefachkraft (w/m/d)", "Fahrer:in"):
        assert "gender-title" not in lint(ok), ok
    assert "german-without-reason" in lint("Koch (m/w/d)", german={"min": "B2"})
    assert "german-without-reason" not in lint("Koch (m/w/d)", german={"min": "B2", "justification": "Hygieneschulung"})


def test_parse_validates():
    base = {"id": "X", "title": "t", "occupation": "koch", "plz": "10115", "start_by": "2026-12-01"}
    jobs.parse(base)
    for bad in (
        {"occupation": "astronaut"},
        {"plz": "00000"},
        {"shifts": ["siesta"]},
        {"must": {"licences": ["Z"]}},
        {"german_level": {"min": "native"}},
    ):
        with pytest.raises(ValueError):
            jobs.parse({**base, **bad})


@pytest.mark.parametrize(
    "text,rule",
    [
        ("Wir erwarten Deutsch auf muttersprachlichem Niveau.", "origin-native-language"),
        ("Accent-free German is a must.", "origin-native-language"),
        ("Nur mit deutschem Pass.", "origin-nationality"),
        ("EU citizens only.", "origin-nationality"),
        ("Du bist zwischen 25 und 40 Jahre alt.", "age"),
        ("Altersgrenze 45 Jahre.", "age"),
        ("Verstärke unser junges, motiviertes Schichtteam.", "age"),
        ("Wir suchen einen kräftigen Mann fürs Lager.", "gender-only"),
        ("We are looking for a reliable woman for reception.", "gender-only"),
        ("Bitte teilen Sie uns mit, ob Sie Kinder haben.", "family"),
        ("Voraussetzung: keine gesundheitlichen Einschränkungen.", "pregnancy-health"),
        ("Bitte Angaben zu einer Schwerbehinderung beifügen.", "pregnancy-health"),
        ("Mitgliedschaft in einer christlichen Kirche erwünscht.", "religion"),
        ("Bewerbung bitte mit aktuellem Lichtbild.", "photo"),
        ("Sie sind mindestens 1,80 m groß.", "physical"),
    ],
)
def test_patterns_cover_how_ads_phrase_each_problem(text, rule):
    assert rule in lint("Lagerist (m/w/d)", text)


@pytest.mark.parametrize(
    "text",
    [
        "Wir fragen nicht nach Familienstand, Alter oder Herkunft.",
        "Unser Team ist zwischen 22 und 63 Jahre alt und kommt aus acht Ländern.",
        "Ein Gesundheitszeugnis nach § 43 IfSG ist Voraussetzung.",
        "Wir freuen uns auf Frauen und Männer, die gerne anpacken.",
        "Schwerbehinderte Menschen werden bei gleicher Eignung bevorzugt berücksichtigt.",
        "Berufseinsteiger und Quereinsteiger sind willkommen. Die Arbeit ist körperlich anstrengend, Sie heben bis 25 kg.",
    ],
)
def test_clean_ads_stay_clean(text):
    assert lint("Lagerist (m/w/d)", text) == {}


def test_one_gender_job_title_in_the_text_needs_an_unmarked_ad():
    assert "gender-only" in lint("Verkäuferin", "Wir suchen eine freundliche Verkäuferin.")
    assert "gender-only" not in lint("Verkäufer (m/w/d)", "Als Verkäufer*in berätst du Kundschaft.")
