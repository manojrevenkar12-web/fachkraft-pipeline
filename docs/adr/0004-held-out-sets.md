# 0004: Blind held-out sets with first runs that are never rewritten

Status: accepted

## Context

The person who writes an extractor also writes the examples it is tested on; those examples
measure the author's imagination, not the candidates'. The simulator has the same limit.

## Decision

- Held-out sets (`heldout/<set>`) are written by someone who has not seen the code, from
  `heldout/WRITING_MESSAGES.md` or `heldout/WRITING_JOBADS.md` only.
- `fkp heldout` records the first run in `reports/heldout/<set>/first_run.json`; it is never
  overwritten, later runs go to `latest.json`.
- Studying a set's failures turns it into a regression set (`STATUS` = `regression`) and calls
  for a new blind set. `jobads-v1` went that way: the AGG checker was rebuilt from word lists to
  patterns, and the new blind `jobads-v2` measured it (recall 55% → 73%).

## Consequences

The README reports first runs, including the weak ones (health redaction 5 of 9 on
`messages-v1`). Improvements are claimed only when a new blind set confirms them.
