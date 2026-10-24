# fachkraft-pipeline

A WhatsApp-first hiring engine for skilled and semi-skilled workers in Germany. Candidates write
the way they write to a friend, in German, Turkish, Polish, Romanian, Ukrainian, Russian, Arabic
or English. The assistant asks for consent, reads what it can from free text, asks only what the
job still needs, reads the profile back for correction, matches it against open jobs with a
reason for every verdict, and hands the candidate to the ATS (Personio, or any system through a
signed webhook or n8n). Recruiters work in a German web app that shows, for every fact, the
words in the chat it came from.

![Candidate view: every fact links to the words in the chat it was read from](docs/img/candidate.png)

## Why this shape

Blue-collar applicants apply from a phone or not at all: in a forsa survey for onlyfy (2023),
45% of blue-collar workers said applying by mobile matters to them and one in five would rather
apply without a CV, while 31% of the companies asked already recruited over WhatsApp. The
Bundesagentur für Arbeit's latest bottleneck analysis (September 2026) counts 157 shortage
occupations, led by care, construction trades, cooks, professional drivers and early-years
educators, the occupations this engine knows, and many candidates for them are not native German
speakers. DACH vendors (chatarmin, softgarden's chat recruiting, talentsconnect's ChatAgent and
others) converge on short, consent-first chats with an ATS hand-over. What they leave open is
what this repository works on:

- **Free text instead of a form.** A form bot asks every field one message at a time. Here one
  open answer usually fills half the profile, and the follow-up questions depend on the job:
  a nurse with a foreign qualification is asked about recognition (Anerkennung), a driver about
  CE and Code 95, nobody about things the job does not need.
- **Evidence for every value.** Each fact carries the span of the message it was read from. The
  recruiter sees it highlighted in the chat; the ATS receives it next to the value.
- **Models read, code decides.** The offline rules extractor reads eight languages without any
  model. An optional Claude extractor fills only fields the rules left empty, must quote the
  message for every value (unquoted or out-of-vocabulary values are dropped), and never sees
  sentences about health. Matching, eligibility and every message sent are decided by code
  over `config/`.
- **German law in the loop.** The AI Act's transparency duty (Art. 50) is the first sentence of
  every chat. GDPR consent comes before anything is read; "stop" in any language erases
  everything; health sentences are removed before storage (Art. 9). Job ads are checked against
  the AGG before they can be published, and a German level filters candidates only when the job
  says why it needs it ("Deutsch als Muttersprache" is origin discrimination, LAG Hessen,
  16 Sa 1619/14).
- **WhatsApp's rules and prices.** Free-form messages only inside the 24-hour customer-service
  window; outside it only the approved utility template, re-checked at send time; error 131047
  expires a message instead of retrying it. Reminders respect quiet hours, Sundays and public
  holidays. Since 1 October 2026 Meta charges service messages beyond 1,000 a month per number
  and utility templates inside the window, so every message the assistant does not have to send
  is money; every outbound message records the category Meta billed.

## Results

All numbers below are produced by commands in this repository and committed under `reports/`.

### Conversation and matching: simulation (`fkp eval`)

600 simulated candidates with a hidden true profile, in eight languages, played through the real
dialogue code; the same candidates also go through a fixed WhatsApp form bot (assumed to read
every answer perfectly) and through keyword forwarding (occupation title and city, as a job board
alert or simple ATS filter does). Drop-off and reminder behaviour are stated assumptions, the same
for both flows. The candidate phrasings were written by the author of the extractor, so this
measures conversation mechanics and matching, not reading accuracy (that is the next section).

| | Assistant | Form bot |
|---|---:|---:|
| Reached a decision (hand-over, talent pool or no match) | 79.7% | 73.7% |
| Messages the candidate had to send (median) | 9 | 14 |
| Time to a decision (median) | 8.0 h | 25.6 h |
| Messages sent by the business | 4,611 | 7,955 |
| WhatsApp cost per candidate who reached a decision, above 1,000 service messages a month | €0.45 | €0.87 |

| What reaches a recruiter | Assistant | Keyword forwarding |
|---|---:|---:|
| Candidate–job pairs forwarded | 139 | 295 |
| Of those, deserved on the true profile | 89.2% | 56.9% |
| Deserving candidates reached | 73.8% | 100% |

Keyword forwarding reaches everyone because it forwards everyone in the right occupation and
city; a recruiter then screens 295 pairs to find 168. The assistant forwards half as many, nine
in ten of them deserved, and loses the candidates who stopped answering. The 11% it forwards
wrongly are mostly candidates who skipped a question: an unknown requirement goes to the
recruiter as a "near" match on purpose, with the open point named.

### Reading unseen messages and ads: blind held-out sets (`fkp heldout`)

Held-out sets are written by someone who has not seen the code, from `heldout/WRITING_*.md`
only; their first run is recorded and never rewritten.

| Set | First run |
|---|---|
| `messages-v1`: 200 candidate messages, 8 languages, offline rules only | precision 89.3%, recall 70.6%, 55% of messages read exactly; language detected 99.0%; stop/human intents 16 of 19, none false; health mentions redacted 5 of 9 |
| `jobads-v1`: 100 job ads (AGG) | precision 95.6%, recall 55.1%; publish/block decision 76% right |
| `jobads-v2`: 120 new ads, after the checker was rebuilt | precision 94.4%, recall 73.1%; publish/block decision 85% right (15 should-have-been-blocked ads published, 3 clean ads blocked) |

What this says:

- The offline reader is precise but misses about 30% of facts in wording it has not seen. Each
  miss costs one extra question, not a wrong match; that is the job the optional Claude extractor
  is built for. Its share of the recall is not reported here, because measuring it needs an API
  key and a fresh blind set.
- Health redaction missed 4 of 9 mentions in the blind set; a general vocabulary pass since then
  catches 6 of 9 on the same set (`latest.json`), a number that is no longer blind. Until a new
  blind set says otherwise, treat stored messages as possibly containing health text.
- The AGG checker went from word lists (v1) to patterns (v2) after v1 was studied, so v1 is now
  a regression set. On a fresh blind set recall rose from 55% to 73%, and a quarter of the ads
  that should be blocked still pass. The checker is a first line that catches the common
  wordings, not legal review.

### Tests

133 Python tests (16 of them against PostgreSQL: exactly-once inbound processing under
concurrency, outbox leases and retries, the 24-hour window and error 131047, reminders,
erasure, retention, health never stored) and 18 web tests. CI runs lint, types, all tests, checks
that the committed simulation report is reproducible, and builds both images.

## The conversation

```
Candidate: J-LKW-LEJ Hallo, bin LKW-Fahrer mit CE und Code 95, wohne in Leipzig, kann ab sofort
Assistant: Hallo Alex! Ich bin der digitale Assistent von … eine KI, kein Mensch. … Bist du einverstanden?
           [Ja, los geht's] [Nein danke]
Candidate: [Ja, los geht's]
Assistant: Welche Schichten gehen für dich: früh, spät, nachts, Wochenende?       ← occupation, licences, home,
Candidate: früh und spät, keine Nacht                                               start were in the first message
Assistant: Ich habe notiert: • Beruf … • Führerscheine/Scheine: B, C, CE, Code 95 … Stimmt das so?
…
Assistant: Danke! Du passt zu: Berufskraftfahrer CE (m/w/d) Nahverkehr. Jemand aus dem Team meldet sich bis 27.10.2026 bei dir.
```

1. **Consent first** (`dialogue.py`). The first reply says it is an AI, what the data is for and
   for how long, and asks for consent. Nothing is read before the yes; the first message is kept
   and read after it, so its facts are not asked again.
2. **One open question, then targeted ones.** The required fields come from the target job (or
   the candidate's occupation): recognition only for regulated occupations, licences only where
   the job needs them, a German level only where the job justifies one. At most seven questions;
   a question answered with something else is asked once more, then skipped.
3. **Read-back.** The candidate confirms or corrects in their own words; two failed corrections
   hand the chat to a person.
4. **Match** (`matching.py`). Hard requirements decide; a gap usually closed within weeks (Code 95,
   forklift licence, recognition under way, a start up to a month late, German one level below)
   makes a "near" match for a recruiter instead of a rejection. Matching sees only an allowlist
   of fields; a test changes name, phone, email and language and checks nothing moves.
5. **Hand-over** with a reply date in business days (holidays per state), or the talent pool
   with a separate yes, or deletion.

## Architecture

```mermaid
flowchart LR
  WA[WhatsApp Cloud API] -- webhook, signed --> API
  SBX[Web app: Chat testen] -- sandbox channel --> API
  API[FastAPI] -- one transaction per message --> PG[(PostgreSQL)]
  PG --> W[Outbox worker<br/>SKIP LOCKED + lease]
  W -- free-form or template --> WA
  W -- signed JSON / Personio API --> ATS[Personio / n8n / any ATS]
  API --> APP[Recruiter web app]
  subgraph engine [same code everywhere]
    D[dialogue.Agent<br/>pure, time passed in] --> X[extract: rules, optional Claude]
    D --> M[matching]
  end
  API --- engine
```

- **Exactly once.** Each inbound message is deduplicated by its WhatsApp id and processed under a
  per-number advisory lock, in one transaction with the replies, events and hand-overs it causes
  (`engine.py`). Two webhooks for the same person serialise; a retried webhook is a no-op.
- **Outbox.** Replies, ATS hand-overs and event webhooks are rows. Workers claim them with
  `FOR UPDATE SKIP LOCKED` and a 60-second lease, send outside the transaction, retry with
  backoff (30 s · 2ⁿ, at most 8 attempts), and a crashed worker's rows return when the lease ends.
- **Same code everywhere.** `dialogue.Agent` is pure: no database, no network, time passed in.
  The webhook, the sandbox, the terminal chat (`fkp chat`) and the simulator all run it.

## Run it

```bash
docker compose up --build        # Postgres, API, worker, web app on http://localhost:8080
# key: local-admin-key-change-me
```

Development:

```bash
pip install -e ".[dev]"
export FKP_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/fkp_test
pytest -q                                   # 133 tests; the 16 database tests need PostgreSQL
fkp chat --job J-LKW-LEJ                    # talk to the assistant in the terminal, no database
fkp eval                                    # simulation report into reports/
fkp heldout heldout/jobads-v2               # run a held-out set (the first run is kept)
FKP_DATABASE_URL=… fkp demo --n 70          # fill a database with simulated candidates

cd web && npm ci && npm test && npm run dev # web app on :5173, proxies /api to :8000
```

Settings live in `config/`: company, retention, reminder schedule, quiet hours, WhatsApp prices
and templates (`settings.yaml`), messages in eight languages (`messages.yaml`), vocabularies
(`lexicon.yaml`, `occupations.yaml`, `cities.yaml`), AGG patterns (`agg.yaml`) and jobs.
Secrets come from the environment (`.env.example`).

## Integrations

- **WhatsApp Business Platform (Cloud API).** `GET/POST /webhooks/whatsapp` with signature check
  (`X-Hub-Signature-256`), text, reply buttons, voice notes (asked to write instead), images and
  documents; delivery statuses with pricing category. Templates: `application_missing_info`
  (utility; it must stay free of promotion, because Meta can recategorise a utility template
  with promotional content as marketing, at 2.5 times the price) and `pool_match` (marketing, only for talent-pool members who said yes).
- **Personio.** `POST /v1/recruiting/applications` with first name, last name, email and the
  Personio position id mapped from the job (`FKP_PERSONIO_POSITIONS`); name and email are asked
  only after a job fits. 429 and 5xx are retried, 4xx is not.
- **Anything else, including n8n and Make.** A signed JSON webhook (`X-FKP-Signature: sha256=…`,
  `Idempotency-Key`) for hand-overs and events. `integrations/n8n/handover.json` is a workflow
  that verifies the signature and appends the candidate to a sheet. See
  [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

## Data protection

| Data | Where it goes | How long |
|---|---|---|
| Messages before consent | stored, not read | 72 hours |
| Profile, messages (health sentences removed) | database, recruiter app | until a decision; rejected: 6 months |
| Talent pool | only with a separate yes | 6 months |
| Hand-over | ATS: profile with evidence, checks, consent time; never the chat or health text | the ATS's rules |
| "Stop" | everything erased; the number kept as a salted hash so no reminder reaches it | until they write again |

Recruiters can export everything stored about a person (Art. 15) and erase it (Art. 17) from the
API. The web app loads no third-party resources: fonts are self-hosted, because embedding Google
Fonts was held to breach the GDPR (LG München I, 3 O 17493/20).

## Repository map

```
src/fkp/        dialogue.py (the conversation), extract/ (rules, Claude), matching.py, jobs.py (AGG),
                engine.py (transactions, outbox), api.py, whatsapp.py, ats.py, privacy.py, calendar.py,
                sim/ (personas, form bot, evaluation, demo data), heldout.py, cli.py
config/         everything a business owner would change
web/            recruiter app: React, TypeScript, Framer Motion; feature folders, tokens, tests
heldout/        blind-written sets and the guides to write them
reports/        simulation and held-out results (first runs are never rewritten)
deploy/k8s/     API, worker, migration job, web, ingress
docs/           decisions (adr/), runbook, integrations
```

## Sources

- Candidates and companies: [forsa / onlyfy blue-collar study, Nov 2023](https://onlinemarketing.de/karriere/human-resources/blue-collar-recruiting-beduerfnisse) ·
  [Bundesagentur für Arbeit, Engpassanalyse, Sep 2026](https://www.arbeitsagentur.de/presse/2026-32-fachkraefte-bleiben-knapp-zuwanderung-gewinnt-weiter-an-bedeutung)
- Conversational recruiting in DACH: [chatarmin](https://chatarmin.com/loesungen/whatsapp-recruiting) ·
  [softgarden chat recruiting](https://softgarden.com/en/solutions/chat-recruiting) ·
  [OMR Reviews, WhatsApp recruiting tools](https://omr.com/de/reviews/category/whatsapp-recruiting)
- WhatsApp: [Meta, pricing and the October 2026 changes](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing) ·
  [German EUR rates from October 2026 (meetergo summary)](https://help.meetergo.com/en/integrations/automation/whatsapp-pricing) ·
  [template category guidelines](https://www.ycloud.com/blog/whatsapp-api-message-template-category-guidelines-update)
- AI Act after the Digital Omnibus (Art. 50 from 2 Aug 2026, Annex III employment from 2 Dec 2027):
  [Cooley](https://cdp.cooley.com/digital-ai-omnibus-delays-key-deadlines-introduces-new-rules/)
- Personio: [creating applications](https://developer.personio.de/v1.0/reference/post_v1-recruiting-applications)
- AGG: [LAG Hessen, 16 Sa 1619/14 (judgment)](https://www.dgbrechtsschutz.de/fileadmin/media/0_2015_Media_Neu/PDF/Urteile/Hessisches_Landesarbeitsgericht_16_Sa_1619-14.pdf) ·
  [Tagesspiegel report](https://www.tagesspiegel.de/gesellschaft/panorama/deutsch-als-muttersprache-in-stellenanzeige-ist-diskriminierend-2640316.html)
- Google Fonts and the GDPR: [LG München I, 3 O 17493/20 (IHK summary)](https://www.ihk.de/bergische/recht-und-steuern/wettbewerbsrecht/google-fonts-5646176)
- Recognition of foreign qualifications: [Anerkennung in Deutschland](https://www.anerkennung-in-deutschland.de)
- Postcodes: GeoNames via [zauberware/postal-codes-json-xml-csv](https://github.com/zauberware/postal-codes-json-xml-csv) (CC BY 4.0)
