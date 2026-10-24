"""Synthetic candidates with a hidden true profile, and how they answer.

The phrasings here are a model of how people write, built by the same author as the extractor, so
the simulation measures the *conversation mechanics* (how many questions, what reaches the ATS,
what a form bot would have needed), not how well the extractor reads unseen wording. That is what
the blind held-out sets in heldout/ are for.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .. import geo

LANG_MIX = {"de": 0.38, "tr": 0.12, "pl": 0.12, "ro": 0.12, "uk": 0.08, "ru": 0.06, "ar": 0.07, "en": 0.05}
OCCUPATIONS = {
    "berufskraftfahrer": {"licences": [["B", "C", "CE", "code95"], ["B", "C", "CE"], ["B", "C"]], "near": "04109"},
    "pflegefachkraft": {"licences": [["B"], []], "near": "10249"},
    "pflegehelfer": {"licences": [["B"], []], "near": "10319"},
    "elektroniker": {"licences": [["B"]], "near": "80331"},
    "lagerlogistik": {"licences": [["forklift", "B"], ["forklift"], ["B"]], "near": "44135"},
    "anlagenmechaniker_shk": {"licences": [["B"], []], "near": "20095"},
    "koch": {"licences": [[]], "near": "50667"},
    "schweisser": {"licences": [["B"]], "near": "70173"},
}
NEARBY = {
    "04109": ["04315", "04229", "04157", "06108", "01067"], "10249": ["10247", "10405", "12043", "13353", "14467"],
    "10319": ["10315", "10318", "12681", "10247", "12555"], "80331": ["80689", "81369", "85049", "86150", "80939"],
    "44135": ["44137", "44227", "44787", "45127", "58095"], "20095": ["22083", "21073", "22765", "23552", "24103"],
    "50667": ["50823", "51063", "53111", "40213", "52062"], "70173": ["70372", "71032", "72764", "74072", "89073"],
}
OCC_WORD = {
    "de": {"berufskraftfahrer": "LKW-Fahrer", "pflegefachkraft": "Pflegefachkraft", "pflegehelfer": "Pflegehelferin", "elektroniker": "Elektriker",
           "lagerlogistik": "Lagerist", "anlagenmechaniker_shk": "Anlagenmechaniker", "koch": "Koch", "schweisser": "Schweißer"},
    "en": {"berufskraftfahrer": "truck driver", "pflegefachkraft": "registered nurse", "pflegehelfer": "care assistant", "elektroniker": "electrician",
           "lagerlogistik": "warehouse worker", "anlagenmechaniker_shk": "plumber", "koch": "cook", "schweisser": "welder"},
    "tr": {"berufskraftfahrer": "tır şoförü", "pflegefachkraft": "hemşire", "pflegehelfer": "hasta bakıcı", "elektroniker": "elektrikçi",
           "lagerlogistik": "depocu", "anlagenmechaniker_shk": "tesisatçı", "koch": "aşçı", "schweisser": "kaynakçı"},
    "pl": {"berufskraftfahrer": "kierowca zawodowy", "pflegefachkraft": "pielęgniarka", "pflegehelfer": "opiekunka", "elektroniker": "elektryk",
           "lagerlogistik": "magazynier", "anlagenmechaniker_shk": "hydraulik", "koch": "kucharz", "schweisser": "spawacz"},
    "ro": {"berufskraftfahrer": "șofer de camion", "pflegefachkraft": "asistentă medicală", "pflegehelfer": "îngrijitoare", "elektroniker": "electrician",
           "lagerlogistik": "lucrător depozit", "anlagenmechaniker_shk": "instalator", "koch": "bucătar", "schweisser": "sudor"},
    "uk": {"berufskraftfahrer": "водій вантажівки", "pflegefachkraft": "медсестра", "pflegehelfer": "доглядальниця", "elektroniker": "електрик",
           "lagerlogistik": "комірник", "anlagenmechaniker_shk": "сантехнік", "koch": "кухар", "schweisser": "зварник"},
    "ru": {"berufskraftfahrer": "водитель грузовика", "pflegefachkraft": "медсестра", "pflegehelfer": "сиделка", "elektroniker": "электрик",
           "lagerlogistik": "кладовщик", "anlagenmechaniker_shk": "сантехник", "koch": "повар", "schweisser": "сварщик"},
    "ar": {"berufskraftfahrer": "سائق شاحنة", "pflegefachkraft": "ممرضة", "pflegehelfer": "مقدمة رعاية", "elektroniker": "كهربائي",
           "lagerlogistik": "عامل مستودع", "anlagenmechaniker_shk": "سباك", "koch": "طباخ", "schweisser": "لحام"},
}
T = {  # sentence frames per language
    "de": {"occ": "Ich bin {x}", "loc": "Ich wohne in {plz} {place}", "exp": "seit {n} Jahren im Beruf", "start_now": "ab sofort",
           "start_date": "ab {d}", "lic": "Führerschein {x}", "lic_none": "keinen Führerschein", "c95": "Code 95", "fork": "Staplerschein",
           "shift_all": "Schichtarbeit ok", "shift_no_night": "Früh- und Spätschicht ja, keine Nachtschicht", "shift_early": "nur Frühschicht",
           "ger": "Deutsch {x}", "rec_in": "Anerkennung läuft", "rec_done": "Abschluss ist anerkannt", "rec_not": "noch keine Anerkennung",
           "dom": "Ausbildung in Deutschland gemacht", "dunno": "weiß ich nicht", "email": "{e}", "greet": "Hallo, ich suche Arbeit"},
    "en": {"occ": "I am a {x}", "loc": "I live in {plz} {place}", "exp": "{n} years of experience", "start_now": "available immediately",
           "start_date": "from {d}", "lic": "driving licence {x}", "lic_none": "no driving licence", "c95": "code 95", "fork": "forklift licence",
           "shift_all": "any shift is fine", "shift_no_night": "early and late shift yes, no night shifts", "shift_early": "early shift only",
           "ger": "German {x}", "rec_in": "recognition in progress", "rec_done": "my qualification is recognised", "rec_not": "not recognised yet",
           "dom": "trained in Germany", "dunno": "not sure", "email": "{e}", "greet": "Hello, I am looking for work"},
    "tr": {"occ": "Mesleğim {x}", "loc": "{plz} {place} oturuyorum", "exp": "{n} yıldır çalışıyorum", "start_now": "hemen başlayabilirim",
           "start_date": "{d} itibaren", "lic": "{x} ehliyetim var", "lic_none": "ehliyetim yok", "c95": "Code 95", "fork": "forklift belgesi",
           "shift_all": "her vardiya olur", "shift_no_night": "sabah ve akşam vardiyası olur, gece vardiyası olmaz", "shift_early": "sadece sabah vardiyası",
           "ger": "Almanca {x}", "rec_in": "denklik başvurusu yaptım", "rec_done": "denklik aldım", "rec_not": "denklik yok",
           "dom": "Almanya'da okudum", "dunno": "bilmiyorum", "email": "{e}", "greet": "Merhaba, iş arıyorum"},
    "pl": {"occ": "Jestem {x}", "loc": "Mieszkam w {place}, {plz}", "exp": "mam {n} lat doświadczenia", "start_now": "mogę od zaraz",
           "start_date": "mogę od {d}", "lic": "prawo jazdy kat. {x}", "lic_none": "nie mam prawa jazdy", "c95": "kod 95", "fork": "uprawnienia UDT na wózek widłowy",
           "shift_all": "każda zmiana pasuje", "shift_no_night": "pierwsza i druga zmiana tak, bez nocek", "shift_early": "tylko poranna zmiana",
           "ger": "niemiecki {x}", "rec_in": "uznanie w toku", "rec_done": "mam uznanie", "rec_not": "nie mam uznania",
           "dom": "szkoła w Niemczech", "dunno": "nie wiem", "email": "{e}", "greet": "Dzień dobry, szukam pracy"},
    "ro": {"occ": "Sunt {x}", "loc": "Locuiesc în {place}, {plz}", "exp": "am {n} ani experiență", "start_now": "pot începe imediat",
           "start_date": "pot începe din {d}", "lic": "permis categoria {x}", "lic_none": "nu am permis", "c95": "cod 95", "fork": "atestat stivuitor",
           "shift_all": "orice tură", "shift_no_night": "tura de dimineață și tura 2 da, fără ture de noapte", "shift_early": "doar tura de dimineață",
           "ger": "germană {x}", "rec_in": "echivalare în curs", "rec_done": "am echivalare", "rec_not": "nu am echivalare",
           "dom": "în germania am învățat", "dunno": "nu știu", "email": "{e}", "greet": "Bună ziua, caut de lucru"},
    "uk": {"occ": "Я {x}", "loc": "Живу в {place}, {plz}", "exp": "досвід {n} років", "start_now": "можу почати одразу",
           "start_date": "можу з {d}", "lic": "посвідчення категорії {x}", "lic_none": "немає посвідчення", "c95": "код 95", "fork": "посвідчення водія навантажувача",
           "shift_all": "будь-яка зміна", "shift_no_night": "ранкова і вечірня зміна так, без нічних", "shift_early": "тільки ранкова зміна",
           "ger": "німецька {x}", "rec_in": "визнання в процесі", "rec_done": "диплом визнали", "rec_not": "немає визнання",
           "dom": "навчалася в Німеччині", "dunno": "не знаю", "email": "{e}", "greet": "Привіт, шукаю роботу"},
    "ru": {"occ": "Я {x}", "loc": "Живу в {place}, {plz}", "exp": "опыт {n} лет", "start_now": "могу начать сразу",
           "start_date": "могу с {d}", "lic": "права категории {x}", "lic_none": "нет прав", "c95": "код 95", "fork": "удостоверение водителя погрузчика",
           "shift_all": "любая смена", "shift_no_night": "утренняя и вечерняя смена да, без ночных", "shift_early": "только утренняя смена",
           "ger": "немецкий {x}", "rec_in": "признание в процессе", "rec_done": "диплом признали", "rec_not": "нет признания",
           "dom": "учился в германии", "dunno": "не знаю", "email": "{e}", "greet": "Здравствуйте, ищу работу"},
    "ar": {"occ": "أنا {x}", "loc": "أسكن في {place} {plz}", "exp": "خبرة {n} سنوات", "start_now": "يمكنني البدء فورا",
           "start_date": "من {d}", "lic": "رخصة {x}", "lic_none": "لا رخصة", "c95": "code 95", "fork": "رخصة رافعة شوكية",
           "shift_all": "كل الورديات", "shift_no_night": "وردية صباحية ومسائية نعم، لا ليلي", "shift_early": "وردية صباحية فقط",
           "ger": "الألمانية {x}", "rec_in": "قيد المعادلة", "rec_done": "تمت معادلة شهادتي", "rec_not": "غير معادلة",
           "dom": "درست في ألمانيا", "dunno": "لا أعرف", "email": "{e}", "greet": "مرحبا، أبحث عن عمل"},
}


@dataclass
class Persona:
    id: str
    lang: str
    truth: dict[str, Any]
    style: str  # terse: one fact per message; chatty: several facts, unasked
    patience: float  # chance of answering each further question at all
    full_name: str
    job_ref: str | None
    rng: random.Random = field(repr=False, default_factory=random.Random)


_SHIFTS = [{"early": True, "late": True, "night": True, "weekend": True},
           {"early": True, "late": True, "night": False},
           {"early": True, "late": False, "night": False}]
_JOB_FOR = {"berufskraftfahrer": "J-LKW-LEJ", "pflegefachkraft": "J-PFK-BER", "pflegehelfer": "J-PH-BER", "elektroniker": "J-ELE-MUC",
            "lagerlogistik": "J-LAG-DO", "anlagenmechaniker_shk": "J-SHK-HH"}
_NAMES = {"de": ["Jonas Becker", "Lea Hoffmann"], "en": ["Sam Taylor", "Grace Okafor"], "tr": ["Ali Yılmaz", "Elif Kaya"],
          "pl": ["Piotr Nowak", "Anna Wiśniewska"], "ro": ["Andrei Popescu", "Ioana Ionescu"], "uk": ["Олена Коваленко", "Андрій Шевченко"],
          "ru": ["Ирина Смирнова", "Дмитрий Иванов"], "ar": ["Omar Haddad", "Lina Khalil"]}


def make(n: int, seed: int, today: date) -> list[Persona]:
    rng = random.Random(seed)
    langs, weights = zip(*LANG_MIX.items(), strict=True)
    everywhere = [p for ps in NEARBY.values() for p in ps]
    out = []
    for i in range(n):
        lang = rng.choices(langs, weights)[0]
        occ = rng.choice(list(OCCUPATIONS))
        spec = OCCUPATIONS[occ]
        plz = rng.choice(NEARBY[spec["near"]] if rng.random() < 0.8 else everywhere)
        place = geo.by_plz(plz)
        assert place is not None, plz
        foreign = lang != "de" and rng.random() < 0.85
        start = today if rng.random() < 0.4 else today + timedelta(days=rng.choice([14, 30, 45, 75]))
        truth: dict[str, Any] = {
            "occupation": [occ],
            "location": {"place": place.name, "plz": place.plz, "lat": place.lat, "lon": place.lon},
            "licences": sorted(rng.choice(spec["licences"])),
            "start_date": start.isoformat(),
            "shifts": dict(rng.choice(_SHIFTS)),
            "german_level": rng.choice(["A2", "B1", "B2", "C1"]) if lang != "de" else "C1",
            "experience_years": rng.randint(1, 15),
            "qualification": "foreign" if foreign else "domestic",
            "email": f"cand{i}@mail.example",
            "_start_now": start == today,
        }
        if occ == "pflegefachkraft" and foreign:
            truth["recognition"] = rng.choice(["recognised", "in_progress", "not_started"])
        job_ref = _JOB_FOR.get(occ) if rng.random() < 0.5 else None
        out.append(Persona(f"p{i:03d}", lang, truth, rng.choice(["terse", "chatty"]), rng.uniform(0.9, 0.99),
                           rng.choice(_NAMES[lang]), job_ref, random.Random(seed * 1000 + i)))
    return out


def phrase(p: Persona, fact: str, today: date) -> str:
    """How this persona says one fact of its true profile."""
    t, v = T[p.lang], p.truth
    if fact == "occupation":
        return t["occ"].format(x=OCC_WORD[p.lang][v["occupation"][0]])
    if fact == "location":
        return t["loc"].format(plz=v["location"]["plz"], place=v["location"]["place"])
    if fact == "experience_years":
        return t["exp"].format(n=v["experience_years"])
    if fact == "start_date":
        d = date.fromisoformat(v["start_date"])
        return t["start_now"] if v["_start_now"] else t["start_date"].format(d=d.strftime("%d.%m.%Y"))
    if fact == "licences":
        lic = v["licences"]
        if not lic:
            return t["lic_none"]
        classes = [x for x in ("B", "C", "C1", "CE", "D") if x in lic]
        parts = [t["lic"].format(x=", ".join(classes))] if classes else []
        if "code95" in lic:
            parts.append(t["c95"])
        if "forklift" in lic:
            parts.append(t["fork"])
        return ", ".join(parts)
    if fact == "shifts":
        s = v["shifts"]
        if s.get("night"):
            return t["shift_all"]
        return t["shift_no_night"] if s.get("late") else t["shift_early"]
    if fact == "german_level":
        return t["ger"].format(x=v["german_level"])
    if fact == "recognition":
        key = {"in_progress": "rec_in", "recognised": "rec_done", "not_started": "rec_not"}.get(v.get("recognition", ""))
        return t[key] if key else t["dom"]
    if fact == "qualification":
        if v["qualification"] == "domestic":
            return t["dom"]
        return phrase(p, "recognition", today) if v.get("recognition") else t["dunno"]
    if fact == "email":
        return str(v["email"])
    if fact == "full_name":
        return p.full_name
    return t["dunno"]


OPEN_FACTS = ["occupation", "location", "experience_years", "start_date", "licences", "german_level"]


def first_message(p: Persona, today: date) -> str:
    base = T[p.lang]["greet"]
    if p.style == "chatty":
        facts = p.rng.sample(OPEN_FACTS[:5], k=p.rng.randint(2, 4))
        base += ". " + ". ".join(phrase(p, f, today) for f in facts)
    return (f"{p.job_ref} " if p.job_ref else "") + base


def open_answer(p: Persona, today: date) -> str:
    k = p.rng.randint(2, 5) if p.style == "chatty" else p.rng.randint(1, 2)
    facts = p.rng.sample(OPEN_FACTS, k=k)
    if "occupation" not in facts and p.rng.random() < 0.7:
        facts.insert(0, "occupation")
    return ", ".join(phrase(p, f, today) for f in facts)
