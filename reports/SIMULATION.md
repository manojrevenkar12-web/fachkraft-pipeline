# Simulation report

600 simulated candidates (seed 7), each with a hidden true profile, in eight languages. This is a simulation: the phrasings were written by the extractor's author, so it measures how the conversation runs and what reaches a recruiter, not how well unseen messages are read. Reading accuracy on blind-written messages is in `reports/heldout/`.

Assumptions, the same for both flows: each further prompt is answered with a per-candidate probability of uniform 0.90–0.99 per prompt; a silent candidate answers a reminder with probability 0.3; 96.0% give consent; reply delays 80% minutes, 15% 1–6 h, 5% 10–18 h; reminders after 20 h, 72 h and 168 h, inside quiet hours and the 24-hour window rules.

## Assistant against a form bot

| | Assistant | Form bot (reads perfectly) |
|---|---:|---:|
| Completed | 79.7% (478) | 73.7% (442) |
| Messages the candidate sent (median, completed) | 9.0 | 14.0 |
| Minutes to done (median) | 481.7 | 1536.2 |
| Reminders, free-form / template | 134 / 132 | 370 / 450 |
| Template cost (utility, USD) | 7.26 | 24.75 |

The assistant handed 139 candidates to a recruiter; template cost per hand-over $0.0522. Candidates corrected the read-back 2 times.

How assistant conversations ended: no job now, joined the talent pool 204; handed to a recruiter 139; stopped answering 130; no job now, data deleted 110; declined consent 17.

## What reaches a recruiter

168 candidates deserve at least one job (fit or near on their true profile).

| | Assistant | Keyword forwarding |
|---|---:|---:|
| Candidate-job pairs forwarded | 139 | 295 |
| Of those, deserved (precision) | 89.2% | 56.9% |
| Deserving candidates reached (recall) | 73.8% | 100.0% |

The assistant's verdict (fit or near) equals the verdict on the true profile for 87.1% of the pairs it forwarded. Keyword recall counts everyone who wrote; the assistant's recall also pays for every candidate who stopped answering.

## Fields, completed conversations

Language detected right: 99.8%. Field values right when present: 100.0%.

| Field | Right | Wrong | Not asked or missing | Accuracy when present |
|---|---:|---:|---:|---:|
| occupation | 478 | 0 | 0 | 100.0% |
| location | 478 | 0 | 0 | 100.0% |
| qualification | 69 | 0 | 409 | 100.0% |
| licences | 209 | 0 | 269 | 100.0% |
| start_date | 478 | 0 | 0 | 100.0% |
| shifts | 478 | 0 | 0 | 100.0% |
| german_level | 432 | 0 | 46 | 100.0% |
| experience_years | 478 | 0 | 0 | 100.0% |
| recognition | 35 | 0 | 0 | 100.0% |

## By language

| Language | Candidates | Completed | Median messages | Field accuracy |
|---|---:|---:|---:|---:|
| de | 213 | 79.8% | 9.0 | 100.0% |
| tr | 75 | 85.3% | 8.0 | 100.0% |
| pl | 75 | 74.7% | 9.0 | 100.0% |
| ro | 75 | 82.7% | 9.0 | 100.0% |
| uk | 42 | 76.2% | 9.0 | 100.0% |
| ru | 43 | 79.1% | 8.5 | 100.0% |
| ar | 40 | 75.0% | 8.0 | 100.0% |
| en | 37 | 81.1% | 8.0 | 100.0% |
