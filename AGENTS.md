# Working on fachkraft-pipeline

Fast feedback: `pytest -q -m "not db"` (seconds), `pytest -q` with `FKP_TEST_DATABASE_URL` set
(PostgreSQL), `cd web && npm test`. `fkp eval` must leave `reports/simulation.json` unchanged
unless the change is meant to move it.

Invariants (each has a test):
- Nothing is read before consent; the first message is read after the yes (`test_dialogue.py`).
- Every profile value carries the message span it came from; model values must quote the message
  and stay in the vocabulary (`test_llm_extractor.py`).
- Matching sees only `matching.feature_allowlist`; name, phone, email and language never change a
  result (`test_matching.py`).
- Health sentences are never stored and never sent to a model (`test_engine.py`, `test_llm_extractor.py`).
- Each inbound WhatsApp message is processed once, under a per-number lock, in one transaction
  with its outbox rows; free-form messages never leave outside the 24-hour window (`test_engine.py`).
- "stop" in any language erases the conversation and suppresses the number by salted hash.
- Thresholds, texts, vocabularies, AGG patterns, prices and schedules live in `config/`, not in code.
- Held-out sets: never change code to pass `heldout/<set>`. First runs in
  `reports/heldout/<set>/first_run.json` are never rewritten. If you study a set's failures, write
  `regression` to its `STATUS` and have someone who has not seen the code write a new set from
  `heldout/WRITING_*.md` only.
- Test and example data: invented people, `.example` domains, nothing sexual, nobody under 18.

Web app: feature folders under `web/src/features`, shared pieces under `web/src/shared`; colours,
sizes and durations come from `web/src/app/theme` tokens; every screen has loading, error and
empty states; all words are in `web/src/shared/text/de.ts`.
