/** Every word the recruiter sees, in one place (German; recruiters work in German). */

export const occupationLabel: Record<string, string> = {
  pflegefachkraft: "Pflegefachkraft", pflegehelfer: "Pflegehelfer/in", erzieher: "Erzieher/in", elektroniker: "Elektroniker/in",
  anlagenmechaniker_shk: "Anlagenmechaniker/in SHK", kfz_mechatroniker: "Kfz-Mechatroniker/in", mechatroniker: "Mechatroniker/in",
  berufskraftfahrer: "Berufskraftfahrer/in", busfahrer: "Busfahrer/in", lagerlogistik: "Fachkraft Lagerlogistik", schweisser: "Schweißer/in",
  koch: "Koch/Köchin", maler: "Maler/in", tischler: "Tischler/in", zerspanungsmechaniker: "Zerspanungsmechaniker/in",
};

export const languageLabel: Record<string, string> = {
  de: "Deutsch", en: "Englisch", tr: "Türkisch", pl: "Polnisch", ro: "Rumänisch", uk: "Ukrainisch", ru: "Russisch", ar: "Arabisch",
};

export const fieldLabel: Record<string, string> = {
  occupation: "Beruf", qualification: "Abschluss", recognition: "Anerkennung", licences: "Führerscheine und Scheine",
  location: "Wohnort", commute_km: "Arbeitsweg", shifts: "Schichten", start_date: "Start", german_level: "Deutsch",
  experience_years: "Berufserfahrung", employment: "Arbeitszeit", email: "E-Mail", full_name: "Name",
};

export const valueLabel: Record<string, string> = {
  domestic: "in Deutschland", foreign: "im Ausland", none: "keiner", trained: "vorhanden", recognised: "anerkannt",
  in_progress: "Verfahren läuft", not_started: "noch nicht beantragt", full_time: "Vollzeit", part_time: "Teilzeit",
  early: "früh", late: "spät", night: "nachts", weekend: "Wochenende", code95: "Code 95", forklift: "Staplerschein", adr: "ADR",
  tachograph_card: "Fahrerkarte",
};

export const checkLabel: Record<string, string> = {
  occupation: "Beruf", recognition: "Anerkennung", licences: "Scheine", commute: "Arbeitsweg", shifts: "Schichten",
  start: "Start", german: "Deutsch", employment: "Arbeitszeit",
};

export const buttonLabel: Record<string, string> = {
  consent_yes: "Ja, einverstanden", consent_no: "Nein, danke", confirm_yes: "Stimmt so", confirm_fix: "Ändern",
  pool_yes: "Ja, in den Talentpool", pool_no: "Nein, löschen",
};

/** "[consent_yes]" (a tapped reply button, as stored) → its label; anything else unchanged. */
export function messageText(body: string): string {
  const m = /^\[([a-z_]+)\]$/.exec(body);
  return m ? `↩ ${buttonLabel[m[1]!] ?? m[1]}` : body;
}

export const verdictLabel = { fit: "passt", near: "fast", unknown: "offen", no: "passt nicht" } as const;

export const groupLabel = {
  ready: "Bereit für dich",
  person: "Will mit einem Menschen sprechen",
  talking: "Im Gespräch mit dem Assistenten",
  pool: "Talentpool",
  closed: "Abgelehnt oder beendet",
} as const;

export const stageLabel: Record<string, string> = {
  new: "neu", awaiting_consent: "wartet auf Einwilligung", declined: "hat abgelehnt", collecting: "beantwortet Fragen",
  confirming: "prüft die Zusammenfassung", fixing: "korrigiert", handover_details: "gibt Kontaktdaten an", pool_question: "Talentpool-Frage",
  handed_over: "übergeben", pooled: "im Talentpool", human: "wartet auf dich", deleted: "gelöscht", closed: "beendet",
};

export const aggRuleLabel: Record<string, string> = {
  "origin-native-language": "Muttersprache verlangt",
  "origin-nationality": "Staatsangehörigkeit oder Herkunft",
  age: "Alter",
  "gender-only": "nur ein Geschlecht angesprochen",
  "gender-title": "Titel ohne (m/w/d)",
  family: "Familienstand oder Kinder",
  "pregnancy-health": "Gesundheit oder Schwangerschaft",
  religion: "Religion",
  photo: "Foto verlangt",
  physical: "Körper statt Tätigkeit beschrieben",
  "german-without-reason": "Deutschniveau ohne Begründung",
};

export const t = {
  product: "Fachkraft Pipeline",
  nav: { candidates: "Bewerbende", jobs: "Stellen", numbers: "Zahlen", sandbox: "Chat testen" },
  signIn: {
    title: "Anmelden",
    lead: "Gib den Zugangsschlüssel ein, den du von der Administration bekommen hast.",
    label: "Zugangsschlüssel",
    submit: "Anmelden",
    signOut: "Abmelden",
  },
  states: {
    retry: "Erneut versuchen",
    loadFailed: "Konnte nicht geladen werden",
  },
  candidates: {
    title: "Bewerbende",
    search: "Name, Ort oder Beruf suchen",
    emptyTitle: "Noch keine Bewerbungen",
    emptyBody: "Sobald jemand über WhatsApp schreibt, erscheint die Person hier. Im Chat-Test kannst du es selbst ausprobieren.",
    emptyAction: "Chat testen",
    noResults: "Niemand passt zu dieser Suche.",
    pickTitle: "Wähle eine Person aus der Liste",
    pickBody: "Du siehst dann, was der Assistent verstanden hat, woher jede Angabe stammt und zu welcher Stelle sie passt.",
    facts: "Was der Assistent verstanden hat",
    factsHint: "Wähle eine Angabe, um die Stelle im Chat zu sehen.",
    noFacts: "Noch keine Angaben. Der Assistent liest erst nach der Einwilligung mit.",
    matches: "Passende Stellen",
    noMatches: "Noch kein Abgleich: das Profil ist noch nicht bestätigt.",
    chat: "Chat",
    consent: "Eingewilligt am",
    noConsent: "Noch keine Einwilligung",
    redacted: "Gesundheitsangaben entfernt",
    reply: "Antwort an die Person",
    send: "Senden",
    sent: "Gesendet",
    windowClosed: "Das 24-Stunden-Fenster ist zu. Erreichen kannst du die Person jetzt nur über eine freigegebene Vorlage.",
    skipped: "übersprungen",
    source: { rules: "Regeln", claude: "Modell" },
    back: "Zur Liste",
  },
  jobs: {
    title: "Stellen",
    emptyTitle: "Noch keine Stellen",
    emptyBody: "Lege die erste Stelle an. Der Text wird beim Schreiben auf diskriminierende Formulierungen geprüft.",
    new: "Neue Stelle",
    open: "offen",
    closed: "geschlossen",
    check: "AGG-Prüfung",
    clean: "Keine Auffälligkeiten.",
    checking: "Wird geprüft …",
    save: "Stelle speichern",
    saved: "Gespeichert",
    blocked: "Diese Formulierungen verhindern das Veröffentlichen. Formuliere sie um oder begründe die Ausnahme.",
    override: "Begründung für die Ausnahme (mindestens 10 Zeichen)",
    fields: {
      id: "Kennung", title: "Titel", occupation: "Beruf", plz: "PLZ", radius: "Umkreis in km", text: "Stellentext",
      german: "Deutsch mindestens", justification: "Warum die Arbeit dieses Niveau braucht", startBy: "Start spätestens", pay: "Vergütung",
    },
    none: "kein Mindestniveau",
  },
  numbers: {
    title: "Zahlen",
    funnel: "Vom ersten Hallo zur Übergabe",
    funnelSteps: { started: "Geschrieben", consented: "Eingewilligt", confirmed: "Profil bestätigt", handed_over: "An dich übergeben" },
    median: "Mittlere Zeit bis zum bestätigten Profil",
    minutes: "Minuten",
    languages: "Sprachen",
    cost: "WhatsApp-Kosten",
    reminders: "Erinnerungen verschickt",
    windowClosed: "Nachrichten nach geschlossenem Fenster",
    side: "Außerdem",
    pooled: "im Talentpool",
    human: "wollten einen Menschen",
    declined: "haben nicht eingewilligt",
    deleted: "Löschungen",
    emptyTitle: "Noch keine Zahlen",
    emptyBody: "Die Auswertung beginnt mit der ersten Nachricht.",
  },
  sandbox: {
    title: "Chat testen",
    lead: "Schreib dem Assistenten wie eine Bewerberin oder ein Bewerber. Das Gespräch läuft durch dasselbe System wie WhatsApp, nur ohne Versand.",
    placeholder: "Nachricht schreiben",
    send: "Senden",
    restart: "Neues Gespräch",
    name: "Name im Chat",
    examples: "Zum Ausprobieren",
    emptyTitle: "Starte das Gespräch",
    emptyBody: "Zum Beispiel mit einer Stellenkennung wie J-LKW-LEJ und ein paar Worten über dich, in einer beliebigen der acht Sprachen.",
    typing: "Assistent schreibt …",
  },
} as const;

export function formatValue(field: string, v: unknown): string {
  if (v === null || v === undefined) return "–";
  if (field === "occupation" && Array.isArray(v)) return v.map((o) => occupationLabel[o] ?? o).join(", ");
  if (field === "location" && typeof v === "object") {
    const l = v as { plz?: string; place?: string };
    return [l.plz, l.place].filter(Boolean).join(" ");
  }
  if (field === "shifts" && typeof v === "object") {
    const s = v as Record<string, boolean>;
    const yes = Object.keys(s).filter((k) => s[k]);
    const no = Object.keys(s).filter((k) => s[k] === false);
    return [yes.map((k) => valueLabel[k] ?? k).join(", "), no.length ? `nicht ${no.map((k) => valueLabel[k] ?? k).join(", ")}` : ""]
      .filter(Boolean).join("; ");
  }
  if (field === "start_date" && typeof v === "string") return new Date(`${v}T12:00:00`).toLocaleDateString("de-DE");
  if (field === "experience_years") return `${v} ${v === 1 ? "Jahr" : "Jahre"}`;
  if (field === "commute_km") return `${v} km`;
  if (Array.isArray(v)) return v.length ? v.map((x) => valueLabel[String(x)] ?? String(x)).join(", ") : "keine";
  return valueLabel[String(v)] ?? String(v);
}

const DETAIL: [RegExp, string][] = [
  [/\bjob needs someone by\b/g, "Stelle braucht jemanden bis"], [/\bjob needs\b/g, "Stelle verlangt"], [/\bneeds\b/g, "verlangt"],
  [/\bmissing\b/g, "fehlt:"], [/\bdoes not work\b/g, "arbeitet nicht"], [/\bworks as\b/g, "arbeitet als"], [/\bstarts\b/g, "Start"],
  [/\bdays after\b/g, "Tage nach"], [/\blimit\b/g, "Grenze"], [/\bwants\b/g, "möchte"], [/\bnot given\b/g, "nicht angegeben"],
  [/\bGerman or recognised qualification\b/g, "deutscher oder anerkannter Abschluss"], [/\brecognition procedure under way\b/g, "Anerkennung läuft"],
  [/\bforeign qualification not yet recognised\b/g, "ausländischer Abschluss noch nicht anerkannt"],
  [/\bno qualification in the occupation\b/g, "kein Abschluss im Beruf"], [/\bGerman\b/g, "Deutsch"],
];

/** Matching explains its checks in English (they also go to the ATS); show them in German. */
export function checkDetail(detail: string): string {
  let out = detail;
  for (const [re, de] of DETAIL) out = out.replace(re, de);
  out = out.replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, "$3.$2.$1");
  return out.replace(/\b[a-z_][a-z0-9_]{2,}\b/g, (w) => occupationLabel[w] ?? valueLabel[w] ?? w);
}
