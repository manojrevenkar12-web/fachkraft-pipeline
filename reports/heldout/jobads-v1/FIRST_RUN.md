# jobads-v1: job ads, held-out (blind, first run)

100 ads. Problems found: precision 95.6%, recall 55.1%. 66 ads with exactly the labelled problems.

Publish/block decision: 76.0% right (15 blocked rightly, 61 published rightly, 23 published that should have been blocked, 1 blocked that were fine).

| Problem | Found | Missed | False | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| age | 5 | 6 | 0 | 100.0% | 45.5% |
| family | 3 | 3 | 1 | 75.0% | 50.0% |
| gender-only | 1 | 6 | 0 | 100.0% | 14.3% |
| gender-title | 12 | 0 | 0 | 100.0% | 100.0% |
| german-without-reason | 8 | 0 | 0 | 100.0% | 100.0% |
| origin-nationality | 1 | 5 | 1 | 50.0% | 16.7% |
| origin-native-language | 4 | 3 | 0 | 100.0% | 57.1% |
| photo | 4 | 2 | 0 | 100.0% | 66.7% |
| physical | 3 | 3 | 0 | 100.0% | 50.0% |
| pregnancy-health | 1 | 4 | 0 | 100.0% | 20.0% |
| religion | 1 | 3 | 0 | 100.0% | 25.0% |
