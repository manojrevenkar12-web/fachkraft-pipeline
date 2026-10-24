# 0001: Models read, code decides

Status: accepted

## Context

A hiring assistant decides things with legal weight: who is forwarded, who is told "no", what is
stored. Under the AI Act, systems that filter or evaluate job applicants are high-risk (Annex III,
applicable from 2 December 2027 after the Digital Omnibus). A model that both reads a message and
decides the match cannot be audited line by line, and it fails differently on every run.

## Decision

- Reading is the only job a model may do, and only the fields the offline rules left empty
  (`extract/llm.py`). Every value must quote the message; a quote that is not in the message, or
  a value outside the vocabulary, is dropped. Reported accuracy comes from the rules alone.
- Everything else is code over `config/`: which questions to ask (`dialogue.required`), the
  match and its reasons (`matching.py`), what reaches the ATS, when to remind, what to delete.
- The match sees only an allowlist of fields; a test changes name, phone, email and language and
  checks the result does not move.

## Consequences

- The system works without an API key, and the held-out numbers measure exactly what runs.
- Recall on unseen wording is limited by the rules (70.6% on `messages-v1`); each miss costs one
  more question, not a wrong decision.
- Turning the model on cannot change a decision rule; it can only fill a field, with a quote a
  recruiter sees.
