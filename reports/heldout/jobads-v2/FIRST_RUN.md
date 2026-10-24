# jobads-v2: job ads, held-out (blind, first run)

120 ads. Problems found: precision 94.4%, recall 73.1%. 93 ads with exactly the labelled problems.

Publish/block decision: 85.0% right (27 blocked rightly, 75 published rightly, 15 published that should have been blocked, 3 blocked that were fine).

| Problem | Found | Missed | False | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| age | 7 | 5 | 0 | 100.0% | 58.3% |
| family | 5 | 2 | 1 | 83.3% | 71.4% |
| gender-only | 6 | 5 | 0 | 100.0% | 54.5% |
| gender-title | 15 | 1 | 0 | 100.0% | 93.8% |
| german-without-reason | 8 | 0 | 0 | 100.0% | 100.0% |
| origin-nationality | 3 | 3 | 0 | 100.0% | 50.0% |
| origin-native-language | 7 | 0 | 0 | 100.0% | 100.0% |
| photo | 6 | 3 | 0 | 100.0% | 66.7% |
| physical | 6 | 1 | 0 | 100.0% | 85.7% |
| pregnancy-health | 2 | 4 | 0 | 100.0% | 33.3% |
| religion | 3 | 1 | 3 | 50.0% | 75.0% |
