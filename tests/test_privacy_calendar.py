from datetime import date

from fkp import calendar, privacy


def test_health_sentences_are_removed_in_several_languages():
    for text, lang in (("Ich bin Pflegehelfer. Ich bin schwanger, deshalb keine Nachtdienste.", "de"),
                       ("I am a welder. I had surgery last year.", "en"),
                       ("Jestem opiekunką. Jestem w ciąży.", "pl"),
                       ("Я медсестра. У мене інвалідність.", "uk")):
        red, hit = privacy.redact(text, lang)
        assert hit and privacy.REMOVED in red and red.split(".")[0] == text.split(".")[0], text


def test_occupation_words_are_not_health():
    for t in ("Ich bin Krankenpfleger", "Pflege von Kranken", "Gesundheits- und Krankenpfleger"):
        assert privacy.redact(t, "de") == (t, False)


def test_phone_hash_ignores_formatting():
    assert privacy.phone_hash("+49 170 1234567") == privacy.phone_hash("00491701234567".lstrip("0"))


def test_holidays_and_business_days():
    assert calendar.easter(2027) == date(2027, 3, 28)
    assert date(2026, 3, 8) in calendar.holidays(2026, "BE") and date(2026, 3, 8) not in calendar.holidays(2026, "BY")
    assert calendar.add_business_days(date(2026, 12, 24), 1) == date(2026, 12, 28)  # 25th and 26th are holidays, 27th Sunday
