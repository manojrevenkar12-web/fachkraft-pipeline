# 0002: Consent before reading; ask only what the next step needs

Status: accepted

## Context

Candidates often put half their profile into the first message, before any consent. GDPR needs a
legal basis before processing; Art. 50 of the AI Act needs people to know they talk to an AI.
Every question costs drop-off and, since October 2026, money (service messages beyond 1,000 a
month are charged).

## Decision

- The first reply discloses the AI, the purpose and retention, and asks for consent with buttons.
  The first message is stored but not read until a yes; then it is read, so its facts are not
  asked again. Without a yes, pre-consent messages are deleted after 72 hours.
- After one open question, the assistant asks only for fields the target job (or the candidate's
  occupation) needs: recognition only for regulated occupations, licences only where required,
  German only where the job justifies a level. At most seven questions.
- Name and email are asked last, and only when a job fits, because only the ATS needs them.

## Consequences

Median nine messages from the candidate against fourteen for a form bot in the simulation. The
question set differs per job, so the recruiter app shows skipped fields instead of assuming a
fixed form.
