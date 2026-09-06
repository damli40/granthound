# Measured (pasted, never typed)

## stats.py

| Measure | Value |
|---|---|
| Runs from: 2026-09-06 (8 of 18 runs in the store) |  |
| Programs watched | 20 |
| Latest run | run-20260906T083424Z at 2026-09-06T08:34:24.853473+00:00 (ok) |
| Runs on record | 8 |
| Verdicts | APPLY 1 · NEEDS_HUMAN 11 · PASS 7 · WATCH 1 |
| Verified live | 5 |
| Verified dead (closed, final call, prior year) | 7 |
| Suspect (stale date, year trap, contradiction) | 7 |
| Unreachable | 1 |
| Not yet checked | 0 |
| Distinct quotes stored (each verbatim-checked against its snapshot) | 72 |
| Programs where a quote had to be dropped | 5 |
| Tokens by node (model) | analyst 126,187 (global.anthropic.claude-sonnet-4-6 126,187) · clerk 42,320 (global.anthropic.claude-haiku-4-5-20251001-v1:0 42,320) · scout 35,311 (global.anthropic.claude-haiku-4-5-20251001-v1:0 35,311) · verifier 341,016 (global.anthropic.claude-haiku-4-5-20251001-v1:0 341,016) |

Generated 2026-09-06T08:37:09.614948+00:00 by scripts/stats.py. Source: /Users/Admin/Desktop/granthound/web/data.json

The cutoff is the first cycle over the full 20-program seed list
(2026-09-06). The 10 earlier runs in the store: 3 failed attempts on
2026-08-23 against a larger Claude model this account cannot use, 3 runs
on 2026-08-23 on Amazon Nova while models were being selected, and 4 runs
(one on 2026-08-23, three on 2026-09-05) on the current Claude Haiku 4.5 /
Claude Sonnet 4.6 pair over the three original seeds. They stay in the
store for history; `scripts/stats.py` with no `--since` flag still reports
on all 18.

## stability.py

(stability compares each program's two latest evaluations across all runs
in the store, not only the runs in the table)

```
akron-community-foundation-competitive-grants None         -> NEEDS_HUMAN  one-run  (None -> year_trap_suspect)
cleveland-foundation-other-grant-opportunities None         -> NEEDS_HUMAN  one-run  (None -> stale_date_suspect)
columbus-foundation-community-garden-grants None         -> PASS         one-run  (None -> verified_dead_closed)
columbus-youth-foundation        None         -> NEEDS_HUMAN  one-run  (None -> year_trap_suspect)
community-foundation-mahoning-valley None         -> NEEDS_HUMAN  one-run  (None -> stale_date_suspect)
dayton-foundation-discretionary-grants None         -> NEEDS_HUMAN  one-run  (None -> page_unreachable)
delaware-county-foundation-oh    None         -> PASS         one-run  (None -> verified_dead_prior_year)
fixtures/sunset-fund             NEEDS_HUMAN  -> APPLY        FLIP  (date_contradiction -> changed_deadline)
greater-toledo-community-foundation None         -> PASS         one-run  (None -> skipped_fit_low_score)
lowes-hometowns                  None         -> NEEDS_HUMAN  one-run  (None -> stale_date_suspect)
muskingum-county-community-foundation None         -> PASS         one-run  (None -> no_program_found)
nea-big-read-arts-midwest        None         -> WATCH        one-run  (None -> verified_live)
provisional-1                    NEEDS_HUMAN  -> PASS         FLIP  (reverified_live -> no_program_found)
provisional-2                    NEEDS_HUMAN  -> PASS         FLIP  (reverified_live -> no_program_found)
provisional-3                    NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
richland-county-foundation       None         -> NEEDS_HUMAN  one-run  (None -> verified_live)
sony-create-action-2024-program  None         -> NEEDS_HUMAN  one-run  (None -> verified_dead_prior_year)
stark-community-foundation-responsive-grants None         -> NEEDS_HUMAN  one-run  (None -> verified_live)
vh1-save-the-music-foundation    None         -> PASS         one-run  (None -> verified_dead_closed)
wayne-county-community-foundation None         -> NEEDS_HUMAN  one-run  (None -> year_trap_suspect)

4 programs with two evals; 3 verdict flip(s).
```
