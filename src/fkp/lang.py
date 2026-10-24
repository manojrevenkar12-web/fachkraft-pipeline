"""Which language a message is written in.

Script first (Arabic; Cyrillic split into Ukrainian and Russian by their own letters), then for
Latin script the letters only one language uses and short function words. Messages that give no
signal keep the conversation's language.
"""

from __future__ import annotations

import re

_UK = set("їієґ")
_RU = set("ыэъё")
_LETTERS = {
    "tr": set("ğşıç"),
    "pl": set("ąęłśżźćń"),
    "ro": set("ășțâî"),
    "de": set("äß"),  # ö and ü are Turkish letters too
}
_WORDS = {
    "de": {
        "hallo",
        "guten",
        "moin",
        "servus",
        "ich",
        "und",
        "bin",
        "habe",
        "nicht",
        "ist",
        "mit",
        "ein",
        "eine",
        "als",
        "seit",
        "jahre",
        "kann",
        "wohne",
        "der",
        "die",
        "das",
        "ja",
        "nein",
        "auch",
        "aber",
        "noch",
        "schon",
        "gelernt",
        "arbeite",
        "führerschein",
    },
    "en": {
        "hello",
        "hi",
        "hey",
        "i",
        "am",
        "and",
        "the",
        "have",
        "my",
        "is",
        "a",
        "an",
        "as",
        "years",
        "can",
        "live",
        "work",
        "yes",
        "no",
        "from",
        "since",
        "with",
        "in",
        "worked",
        "license",
        "licence",
        "im",
        "i'm",
    },
    "tr": {
        "merhaba",
        "selam",
        "iyi",
        "günler",
        "ve",
        "bir",
        "ben",
        "var",
        "yok",
        "değil",
        "degil",
        "evet",
        "hayır",
        "hayir",
        "olarak",
        "yıl",
        "yil",
        "çalışıyorum",
        "calisiyorum",
        "ehliyet",
        "ehliyetim",
        "almanca",
        "de",
        "da",
        "mi",
        "ama",
    },
    "pl": {
        "dzień",
        "dzien",
        "dobry",
        "cześć",
        "czesc",
        "jestem",
        "mam",
        "nie",
        "się",
        "sie",
        "jako",
        "lat",
        "tak",
        "pracuję",
        "pracuje",
        "mieszkam",
        "prawo",
        "jazdy",
        "od",
        "w",
        "z",
        "i",
        "ale",
        "już",
        "juz",
    },
    "ro": {
        "bună",
        "buna",
        "salut",
        "ziua",
        "sunt",
        "am",
        "nu",
        "și",
        "si",
        "în",
        "in",
        "de",
        "cu",
        "ani",
        "lucrez",
        "locuiesc",
        "permis",
        "da",
        "ca",
        "este",
        "pot",
    },
}
_UK_WORDS = {
    "привіт",
    "вітаю",
    "добрий",
    "і",
    "й",
    "це",
    "мене",
    "маю",
    "працюю",
    "років",
    "також",
    "вже",
    "або",
    "що",
    "як",
    "можу",
    "німецька",
    "німецьку",
    "досвід",
    "роботи",
    "зварник",
    "кухар",
    "водій",
    "комірник",
    "доглядальниця",
    "вихователька",
    "почати",
    "одразу",
    "тижні",
    "зміна",
}
_RU_WORDS = {
    "привет",
    "здравствуйте",
    "добрый",
    "и",
    "это",
    "меня",
    "работаю",
    "лет",
    "уже",
    "или",
    "что",
    "как",
    "могу",
    "немецкий",
    "опыт",
    "работы",
    "сварщик",
    "повар",
    "водитель",
    "кладовщик",
    "сиделка",
    "воспитатель",
    "начать",
    "сразу",
    "недели",
    "смена",
    "года",
}
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect(text: str, default: str = "de") -> str:
    letters = [c for c in text.lower() if c.isalpha()]
    if not letters:
        return default
    arabic = sum(1 for c in letters if "؀" <= c <= "ۿ")
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    if arabic >= max(3, len(letters) // 3):
        return "ar"
    if cyr >= max(3, len(letters) // 3):
        words = _TOKEN.findall(text.lower())
        uk = sum(1 for c in letters if c in _UK) + 2 * sum(1 for w in words if w in _UK_WORDS)
        ru = sum(1 for c in letters if c in _RU) + 2 * sum(1 for w in words if w in _RU_WORDS)
        if uk > ru:
            return "uk"
        if ru > uk:
            return "ru"
        return default if default in ("uk", "ru") else "ru"
    score = {lang: 3 * sum(1 for c in letters if c in chars) for lang, chars in _LETTERS.items()}
    score["en"] = 0
    words = _TOKEN.findall(text.lower())
    for w in words:
        for lang, vocab in _WORDS.items():
            if w in vocab:
                score[lang] = score.get(lang, 0) + 1
    best = max(score.items(), key=lambda kv: kv[1])
    ranked = sorted(score.values(), reverse=True)
    if best[1] == 0 or (len(ranked) > 1 and ranked[0] == ranked[1]):
        return default
    return best[0]
