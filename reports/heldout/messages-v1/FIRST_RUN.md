# messages-v1: candidate messages, held-out (blind, first run)

200 messages read with the offline rules (no model). Precision counts wrong and invented values against the reader; recall counts wrong and missed values.

Precision 89.3%, recall 70.6%; 110 of 200 messages read exactly (55.0%); language detected right 99.0%.

Intents (stop, human, yes, no): 16 right, 3 missed, 0 false. Health mentions redacted: 5 of 9, 0 false.

| Field | Right | Wrong | Missed | Invented | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| commute_km | 6 | 0 | 5 | 0 | 100.0% | 54.5% |
| email | 8 | 0 | 0 | 0 | 100.0% | 100.0% |
| employment | 12 | 1 | 2 | 0 | 92.3% | 80.0% |
| experience_years | 22 | 1 | 14 | 1 | 91.7% | 59.5% |
| full_name | 6 | 0 | 0 | 0 | 100.0% | 100.0% |
| german_level | 13 | 2 | 8 | 0 | 86.7% | 56.5% |
| licences | 20 | 2 | 3 | 0 | 90.9% | 80.0% |
| location | 34 | 3 | 3 | 0 | 91.9% | 85.0% |
| occupation | 55 | 1 | 13 | 1 | 96.5% | 79.7% |
| qualification | 10 | 0 | 9 | 3 | 76.9% | 52.6% |
| recognition | 4 | 0 | 7 | 0 | 100.0% | 36.4% |
| shifts | 13 | 6 | 1 | 0 | 68.4% | 65.0% |
| start_date | 13 | 2 | 7 | 3 | 72.2% | 59.1% |

| Language | Messages | Exact | Precision | Recall |
|---|---:|---:|---:|---:|
| ar | 16 | 6 | 92.9% | 52.0% |
| de | 60 | 34 | 87.2% | 70.8% |
| en | 16 | 9 | 84.2% | 72.7% |
| pl | 24 | 12 | 88.0% | 62.9% |
| ro | 24 | 15 | 90.9% | 83.3% |
| ru | 18 | 7 | 78.9% | 57.7% |
| tr | 24 | 14 | 100.0% | 75.0% |
| uk | 18 | 13 | 91.7% | 84.6% |
