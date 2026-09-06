# Measured (pasted, never typed)

## stats.py

| Measure | Value |
|---|---|
| Programs watched | 20 |
| Latest run | run-20260906T083424Z at 2026-09-06T08:34:24.853473+00:00 (ok) |
| Runs on record | 18 |
| Verdicts | APPLY 1 · NEEDS_HUMAN 11 · PASS 7 · WATCH 1 |
| Verified live | 5 |
| Verified dead (closed, final call, prior year) | 7 |
| Suspect (stale date, year trap, contradiction) | 7 |
| Unreachable | 1 |
| Not yet checked | 0 |
| Distinct quotes stored (each verbatim-checked against its snapshot) | 72 |
| Programs where a quote had to be dropped | 5 |
| Tokens by node (model) | analyst 378,446 (global.anthropic.claude-sonnet-4-6 191,058 · global.anthropic.claude-sonnet-5 0 · us.amazon.nova-pro-v1:0 187,388) · clerk 95,913 (global.amazon.nova-2-lite-v1:0 43,006 · global.anthropic.claude-haiku-4-5-20251001-v1:0 52,907) · scout 62,852 (global.amazon.nova-2-lite-v1:0 12,160 · global.anthropic.claude-haiku-4-5-20251001-v1:0 50,692) · verifier 533,840 (global.amazon.nova-2-lite-v1:0 77,035 · global.anthropic.claude-haiku-4-5-20251001-v1:0 456,805) |

Generated 2026-09-06T08:54:13.915256+00:00 by scripts/stats.py. Source: /Users/Admin/Desktop/granthound/web/data.json

## stability.py

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
