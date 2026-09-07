# Measured (pasted, never typed)

## stats.py

| Measure | Value |
|---|---|
| Runs from: 2026-09-06 (12 of 22 runs in the store) |  |
| Programs watched | 20 |
| Latest run | run-20260906T114140Z at 2026-09-06T11:41:40.869884+00:00 (ok) |
| Runs on record | 12 |
| Verdicts | NEEDS_HUMAN 11 · PASS 8 · WATCH 1 |
| Verified live | 6 |
| Verified dead (closed, final call, prior year, no program found) | 7 |
| Suspect (stale date, year trap, contradiction) | 6 |
| Unreachable | 1 |
| Not yet checked | 0 |
| Distinct quotes stored (each verbatim-checked against its snapshot) | 76 |
| Programs where a quote had to be dropped | 5 |
| Tokens by node (model) | analyst 219,590 (global.anthropic.claude-sonnet-4-6 219,590) · clerk 67,192 (global.anthropic.claude-haiku-4-5-20251001-v1:0 67,192) · scout 63,949 (global.anthropic.claude-haiku-4-5-20251001-v1:0 63,949) · verifier 649,256 (global.anthropic.claude-haiku-4-5-20251001-v1:0 649,256) |

Generated 2026-09-06T19:16:54.584241+00:00 by scripts/stats.py. Source: /Users/Admin/Desktop/granthound/web/data.json

The cutoff is the first cycle over the full 20-program seed list
(2026-09-06). The 10 earlier runs in the store: 3 failed attempts on
2026-08-23 against a larger Claude model this account cannot use, 3 runs
on 2026-08-23 on Amazon Nova while models were being selected, and 4 runs
(one on 2026-08-23, three on 2026-09-05) on the current Claude Haiku 4.5 /
Claude Sonnet 4.6 pair over the three original seeds. They stay in the
store for history; `scripts/stats.py` with no `--since` flag still reports
on all 22.

## stability.py

(stability compares each program's two latest evaluations across all runs
in the store, not only the runs in the table)

```
akron-community-foundation-competitive-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
cleveland-foundation-other-grant-opportunities NEEDS_HUMAN  -> NEEDS_HUMAN  same  (stale_date_suspect -> stale_date_suspect)
columbus-foundation-community-garden-grants PASS         -> PASS         same  (verified_dead_closed -> skipped_fit_low_score)
columbus-youth-foundation        NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
community-foundation-mahoning-valley NEEDS_HUMAN  -> NEEDS_HUMAN  same  (stale_date_suspect -> stale_date_suspect)
dayton-foundation-discretionary-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (page_unreachable -> page_unreachable)
delaware-county-foundation-oh    PASS         -> PASS         same  (verified_dead_prior_year -> verified_dead_closed)
fixtures/sunset-fund             APPLY        -> NEEDS_HUMAN  FLIP  (changed_deadline -> reverified_live)
greater-toledo-community-foundation PASS         -> PASS         same  (skipped_fit_low_score -> skipped_fit_low_score)
lowes-hometowns                  NEEDS_HUMAN  -> PASS         FLIP  (stale_date_suspect -> verified_dead_closed)
muskingum-county-community-foundation PASS         -> PASS         same  (no_program_found -> no_program_found)
nea-big-read-arts-midwest        WATCH        -> WATCH        same  (verified_live -> reverified_live)
provisional-1                    PASS         -> PASS         same  (no_program_found -> no_program_found)
provisional-2                    PASS         -> PASS         same  (no_program_found -> no_program_found)
provisional-3                    NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
richland-county-foundation       NEEDS_HUMAN  -> NEEDS_HUMAN  same  (verified_live -> reverified_live)
sony-create-action-2024-program  NEEDS_HUMAN  -> NEEDS_HUMAN  same  (verified_dead_prior_year -> verified_dead_prior_year)
stark-community-foundation-responsive-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (verified_live -> reverified_live)
vh1-save-the-music-foundation    PASS         -> PASS         same  (verified_dead_closed -> verified_dead_closed)
wayne-county-community-foundation NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)

20 programs with two evals; 2 verdict flip(s).
```

All 20 seeds now have two evals apart from the two unattended cycles over
the full seed list (the manual full cycle at 2026-09-06T08:01Z and the
scheduled fire at 2026-09-06T11:38Z); the one-run rows from the previous
export are gone. Of the 2 flips: `fixtures/sunset-fund` is the disclosed
fixture page, changed on purpose to demonstrate a live edit on camera --
its flip is expected, not a finding. `lowes-hometowns` is a real flip: a
stale, no-year deadline that the agent had flagged NEEDS_HUMAN
(`stale_date_suspect`) resolved on the second pass to a confirmed dead
program (`verified_dead_closed`, PASS) -- the kind of resolution this
project is built to catch.

## billing

`aws ce get-cost-and-usage --time-period Start=2026-08-19,End=2026-09-06 --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE`, filtered to Bedrock/Marketplace/Lambda/CloudFront lines:

```
----------------------------------------------------------------
|                        GetCostAndUsage                       |
+---------------------------------------------+----------------+
|  AWS Lambda                                 |  0             |
|  Amazon Bedrock                             |  0             |
|  Amazon Bedrock AgentCore                   |  0.0000000001  |
|  Claude Haiku 4.5 (Amazon Bedrock Edition)  |  -0            |
|  Claude Sonnet 4.6 (Amazon Bedrock Edition) |  -0            |
|  AWS Lambda                                 |  0             |
|  Amazon Bedrock AgentCore                   |  0.0000000001  |
|  Claude Haiku 4.5 (Amazon Bedrock Edition)  |  -0            |
|  Claude Sonnet 4.6 (Amazon Bedrock Edition) |  0             |
+---------------------------------------------+----------------+
```

Two rows per service because MONTHLY granularity split the query's window
at the calendar-month boundary (2026-08-19 to 2026-09-01, then 2026-09-01
to 2026-09-06). Every line shows zero, but that is NOT a measured cost:
Cost Explorer lags roughly 24 hours behind usage, and this query was run
the same day as the two full cycles, so the runs in the table above had
not yet been billed when it ran. `Claude Haiku 4.5 (Amazon Bedrock
Edition)` and `Claude Sonnet 4.6 (Amazon Bedrock Edition)` are the
Marketplace-listed model-access line items (the credit gray zone the brief
calls out); the `-0` is a rounding artifact, not a refund. No CloudFront
line appears in the unfiltered service list for either period.

What the runs would cost at list price, computed from the `node_usage`
token counts stored on the 12 in-scope runs (`--since 2026-09-06`) in
`web/data.json`, at the public on-demand Bedrock rates (Haiku 4.5 $1 per
million input tokens / $5 per million output; Sonnet 4.6 $3 / $15):

| model | input tokens | output tokens | list price |
|---|---|---|---|
| Claude Haiku 4.5 (scout, verifier, clerk) | 754,039 | 26,358 | $0.89 |
| Claude Sonnet 4.6 (analyst) | 202,887 | 16,703 | $0.86 |
| total, 12 runs | 956,926 | 43,061 | $1.75 |

So two full 20-program cycles plus the ten smaller runs cost about $1.75
of model time at list price, before credits; AgentCore, Lambda, DynamoDB,
S3 and CloudFront add fractions of a cent at this scale. Re-run the Cost
Explorer query a day or more after the runs to see the billed figure.
Dami reads the credit balance in the console; this table does not show
it.
