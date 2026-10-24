# Writing a held-out set of candidate messages

A held-out set measures how well the assistant reads WhatsApp messages it has never seen. It is only
honest if the person writing it has **not seen the extractor, its word lists or its tests**. Read
this file and nothing else in the repository.

## What to write

Messages that real applicants for skilled and semi-skilled jobs in Germany would send on WhatsApp:
nurses, care assistants, early-years educators, electricians, plumbers and heating engineers, car
mechanics, mechatronics technicians, truck and bus drivers, warehouse staff, welders, cooks,
painters, joiners and CNC machinists. Write them the way people type on a phone: short, sometimes
without punctuation or capitals, with typos, mixed languages ("Ich bin Fahrer, CE var"), German
words inside other languages, numbers written as digits or words, emoji.

Spread the set over the eight languages, roughly: German 30%, Turkish, Polish and Romanian 12% each,
Ukrainian 9%, Russian 9%, Arabic 8%, English 8%. Write each message in one language (a few German
job words inside it are fine).

Mix three kinds of message:

1. **First messages** (`asked: null`): someone writes about themselves unprompted, one to five
   facts, sometimes none ("Hallo, habt ihr Arbeit?").
2. **Answers** (`asked: <field>`): the reply to one question the assistant asked, for example the
   answer to "Which shifts work for you?". Answers can be one word ("nachts nicht"), can answer
   something else, or can add facts that were not asked.
3. **Hard cases**, at least a quarter of the set: negations ("keine Nachtschicht", "nie mam C"),
   ages next to years of experience ("ich bin 34, seit 8 Jahren Koch"), the same letters meaning
   different things ("C1" the lorry class against "C1" the German level), salary numbers that look
   like postcodes, places that are also words, relative dates ("in zwei Wochen", "nach meiner
   Kündigungsfrist von einem Monat"), corrections ("nein, nicht Köln, Bonn"), someone who wants to
   stop or wants a person, someone who mentions an illness or a pregnancy, someone who writes in a
   language with grammar endings on place names ("w Monachium", "Berlin'de").

Content rules: everyday job-seeking only. Nothing sexual, nobody under 18, no real people's names
(use invented ones), email addresses only at `.example` domains, no phone numbers.

## The file

One YAML file, `cases.yaml`, in a new directory `heldout/messages-vN/` (next free N), plus a file
`STATUS` that contains the single word `heldout`.

```yaml
today: 2026-11-02          # the date the messages are read on; "ab sofort" means this date
cases:
  - id: de-001
    lang: de                # the language you wrote in
    asked: null             # or one of the field names below
    text: "Hallo bin Elektriker aus Augsburg, kann ab 1. Dezember"
    expect:
      occupation: [elektroniker]
      location: {place: Augsburg}
      start_date: 2026-12-01
    intents: []             # optional: stop, human, yes, no
    health: false           # optional: true if the message mentions an illness, disability or pregnancy
```

`expect` lists **every** fact the message states that belongs to one of the fields below, and
nothing else. A fact the message does not state must not appear. If the message states nothing,
write `expect: {}`.

## Fields and values

| Field | Value | Notes |
|---|---|---|
| `occupation` | list of ids from the table below | what the person works as or trained as |
| `qualification` | `none`, `domestic`, `foreign`, `trained` | `domestic`: vocational training or exam done in Germany; `foreign`: done in another country; `none`: no training in the job; `trained` only when the person answers "yes" to the question whether they have a completed training, without saying where |
| `recognition` | `recognised`, `in_progress`, `not_started` | the formal German recognition (Anerkennung) of a foreign qualification |
| `licences` | list from `B`, `BE`, `C1`, `C1E`, `C`, `CE`, `D1`, `D`, `DE`, `code95`, `forklift`, `adr`, `tachograph_card` | write the classes the person names; `[]` if they say they have none. `code95` is the professional driver qualification (Code 95 / Fahrerqualifizierung / Modul 95), `forklift` a forklift licence, `adr` dangerous goods, `tachograph_card` the driver card |
| `location` | `{place: <German name>}` and/or `{plz: "12345"}` | where the person lives (not where they want to work, not where they come from); German spelling of the town ("München", not "Munich") |
| `commute_km` | integer | how far they would travel, in km; for minutes write the minutes as km (30 minutes → 30); scored with ±40% tolerance |
| `shifts` | map of `early`, `late`, `night`, `weekend` to `true`/`false` | only the shifts the message speaks about; "only early shift" is `{early: true, late: false, night: false}`; "any shift" is all four `true` |
| `start_date` | ISO date | the first day they could start; "immediately" is `today`; "next month" is the first of next month; "in two weeks" is today + 14 days |
| `german_level` | `A1`, `A2`, `B1`, `B2`, `C1`, `C2`, or `none` | as stated; words: "a little / basic" → `A2`, "good" → `B2`, "fluent / very good / native" → `C1`, "no German" → `none` |
| `experience_years` | integer | years working in the job; "since 2019" → `today` year minus 2019; never an age |
| `employment` | list of `full_time`, `part_time` | |
| `email` | the address | |
| `full_name` | first and last name | only when `asked: full_name` |

`asked` can be any field name above, or `null`.

Occupation ids:

| id | Job |
|---|---|
| `pflegefachkraft` | registered nurse (Pflegefachkraft, Krankenschwester, Altenpfleger/in with exam) |
| `pflegehelfer` | care assistant |
| `erzieher` | early-years educator (Erzieher/in) |
| `elektroniker` | electrician |
| `anlagenmechaniker_shk` | plumber / heating engineer |
| `kfz_mechatroniker` | car mechanic |
| `mechatroniker` | mechatronics / industrial mechanic |
| `berufskraftfahrer` | truck driver |
| `busfahrer` | bus driver |
| `lagerlogistik` | warehouse staff, forklift driver in a warehouse |
| `schweisser` | welder |
| `koch` | cook / chef |
| `maler` | painter and decorator |
| `tischler` | joiner / carpenter |
| `zerspanungsmechaniker` | CNC machinist |

Intents: `stop` (wants to stop, unsubscribe or have their data deleted), `human` (wants to talk to a
person), `yes` / `no` (a short agreement or refusal, e.g. to "Is that correct?").

## Size and finishing

Write 160 to 220 cases. Do not run the assistant on them. Do not change them after the first run
is recorded: the first run is the honest number. If someone studies the failures afterwards, the
set becomes a regression set (`STATUS` says `regression`) and a new set is written by someone else
from this file.
