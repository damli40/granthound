# Measured (pasted, never typed)

## stats.py

| Measure | Value |
|---|---|
| Runs from: 2026-09-06 (16 of 26 runs in the store) |  |
| Programs watched | 20 |
| Latest run | run-20260906T234110Z at 2026-09-06T23:41:10.603342+00:00 (ok) |
| Runs on record | 16 |
| Verdicts | APPLY 1 · NEEDS_HUMAN 12 · PASS 7 |
| Verified live | 5 |
| Verified dead (closed, final call, prior year, no program found) | 8 |
| Suspect (stale date, year trap, contradiction) | 6 |
| Unreachable | 1 |
| Not yet checked | 0 |
| Distinct quotes stored (each verbatim-checked against its snapshot) | 65 |
| Programs where a quote had to be dropped | 7 |
| Tokens by node (model) | analyst 289,066 (global.anthropic.claude-sonnet-4-6 289,066) · clerk 104,938 (global.anthropic.claude-haiku-4-5-20251001-v1:0 104,938) · scout 87,913 (global.anthropic.claude-haiku-4-5-20251001-v1:0 87,913) · verifier 912,548 (global.anthropic.claude-haiku-4-5-20251001-v1:0 912,548) |

Generated 2026-09-07T00:16:03.572483+00:00 by scripts/stats.py. Source: /Users/Admin/Desktop/granthound/web/data.json

The cutoff is the first cycle over the full 20-program seed list
(2026-09-06). The 10 earlier runs in the store: 3 failed attempts on
2026-08-23 against a larger Claude model this account cannot use, 3 runs
on 2026-08-23 on Amazon Nova while models were being selected, and 4 runs
(one on 2026-08-23, three on 2026-09-05) on the current Claude Haiku 4.5 /
Claude Sonnet 4.6 pair over the three original seeds. They stay in the
store for history; `scripts/stats.py` with no `--since` flag still reports
on all 26.

## stability.py

(stability compares each program's two latest evaluations across all runs
in the store, not only the runs in the table)

```
akron-community-foundation-competitive-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
cleveland-foundation-other-grant-opportunities NEEDS_HUMAN  -> NEEDS_HUMAN  same  (stale_date_suspect -> stale_date_suspect)
columbus-foundation-community-garden-grants PASS         -> PASS         same  (skipped_fit_low_score -> verified_dead_closed)
columbus-youth-foundation        NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
community-foundation-mahoning-valley NEEDS_HUMAN  -> NEEDS_HUMAN  same  (stale_date_suspect -> stale_date_suspect)
dayton-foundation-discretionary-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (page_unreachable -> page_unreachable)
delaware-county-foundation-oh    PASS         -> PASS         same  (verified_dead_closed -> verified_dead_closed)
fixtures/sunset-fund             NEEDS_HUMAN  -> APPLY        FLIP  (reverified_live -> reverified_live)
greater-toledo-community-foundation PASS         -> PASS         same  (skipped_fit_low_score -> skipped_fit_low_score)
lowes-hometowns                  PASS         -> PASS         same  (verified_dead_closed -> verified_dead_closed)
muskingum-county-community-foundation PASS         -> PASS         same  (no_program_found -> no_program_found)
nea-big-read-arts-midwest        WATCH        -> NEEDS_HUMAN  FLIP  (reverified_live -> watch_coming_soon)
provisional-1                    PASS         -> PASS         same  (no_program_found -> no_program_found)
provisional-2                    PASS         -> PASS         same  (no_program_found -> no_program_found)
provisional-3                    NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)
richland-county-foundation       NEEDS_HUMAN  -> NEEDS_HUMAN  same  (reverified_live -> reverified_live)
sony-create-action-2024-program  NEEDS_HUMAN  -> NEEDS_HUMAN  same  (verified_dead_prior_year -> verified_dead_closed)
stark-community-foundation-responsive-grants NEEDS_HUMAN  -> NEEDS_HUMAN  same  (reverified_live -> reverified_live)
vh1-save-the-music-foundation    PASS         -> NEEDS_HUMAN  FLIP  (verified_dead_closed -> verified_dead_closed)
wayne-county-community-foundation NEEDS_HUMAN  -> NEEDS_HUMAN  same  (year_trap_suspect -> year_trap_suspect)

20 programs with two evals; 3 verdict flip(s).
```

Three full-seed-list cycles are on record now, not two: 2026-09-06T08:01Z,
2026-09-06T11:38Z, and 2026-09-06T23:38Z. Only the last two are scheduler
fires -- the 08:01Z cycle was started by hand and must never be called
unattended. The 08:01Z cycle's own program list still differed from the
other two: it ran `walmart-spark-good-local-grants` and had not yet added
`wayne-county-community-foundation`. Both `wayne-county-community-foundation`
and `fixtures/sunset-fund` got their first full-seed-era eval from a
single-program catch-up run instead of from 08:01Z itself (08:05Z and
08:34Z respectively), so the "previous pair" comparison below reads those
two programs' earlier side off those catch-up runs, not off the manual
cycle.

The table above's 3 flips are between the two latest cycles, 11:38Z ->
23:38Z. The previous pair, 08:xx -> 11:38Z, had 2 flips of its own:
`fixtures/sunset-fund` APPLY -> NEEDS_HUMAN and `lowes-hometowns`
NEEDS_HUMAN -> PASS. That is 5 flips across both pairs, and only one of
them is a real change in the program's status:

- `fixtures/sunset-fund`, 08:xx -> 11:38Z (APPLY -> NEEDS_HUMAN): the
  fixture's page had already been reworded before 08:34Z, and that pass
  correctly read the new wording (`changed_deadline`, APPLY). The page did
  not change again before 11:38Z -- what changed was that the Clerk's
  structured output failed to parse that cycle (flag `clerk_missing`), and
  the boundary rule routed the unparseable output to NEEDS_HUMAN. No
  sentence anywhere should attribute this flip to the deliberate page
  edit -- that edit is a different, earlier transition, not this one.
- `fixtures/sunset-fund`, 11:38Z -> 23:38Z (NEEDS_HUMAN -> APPLY): the same
  unchanged page, reverified cleanly this time (`reverified_live`, no
  flags) -- the model recovering, not a new edit.
- `nea-big-read-arts-midwest`, 11:38Z -> 23:38Z (WATCH -> NEEDS_HUMAN): the
  page's diff receipt records no change; a quote from the Analyst or the Clerk was not found
  verbatim in that cycle's snapshot (flags `analyst_quotes_unverified`,
  `clerk_quotes_unverified`).
- `vh1-save-the-music-foundation`, 11:38Z -> 23:38Z (PASS -> NEEDS_HUMAN):
  the diff receipt did record a change (three Cloudflare email-obfuscation
  tokens rotating; `date_lines_changed: false`), but no wording a reader
  sees; what changed the verdict was that a Verifier quote was not found
  verbatim in that cycle's snapshot (flag `verifier_quotes_unverified`).

The fifth and only real one: `lowes-hometowns`, 08:xx -> 11:38Z
(NEEDS_HUMAN -> PASS), a stale no-year deadline resolved on the next pass
to a confirmed dead program (`verified_dead_closed`) -- the kind of
resolution this project is built to catch.

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
to 2026-09-06). Every line shows zero, but that query's window explains
why on its own: `End=2026-09-06` is exclusive in Cost Explorer's API, so
no run made on 2026-09-06 -- which is every run this report counts -- ever
fell inside that window. That is a window-boundary artifact, not a
billing lag. A follow-up query, correctly windowed
(`Start=2026-09-01,End=2026-09-08`, DAILY granularity), run
2026-09-07T01:30 WAT, still shows no Bedrock/Marketplace/Lambda/CloudFront
service line at or above $0.001 on any day in that range. Both facts
stand at once: the first query's zeros proved nothing either way, and the
second, correctly-windowed query genuinely shows nothing billed yet at
that threshold. `Claude Haiku 4.5 (Amazon Bedrock Edition)` and `Claude
Sonnet 4.6 (Amazon Bedrock Edition)` are the Marketplace-listed
model-access line items (the credit gray zone the brief calls out); the
`-0` is a rounding artifact, not a refund. List price, below, is the only
cost figure this report has.

What the runs would cost at list price, computed from the `node_usage`
token counts stored on the 16 in-scope runs (`--since 2026-09-06`; 12
chunks of the three full cycles plus four single-program runs; the ten
earlier runs are not in this total) in `web/data.json`, at the public
on-demand Bedrock rates (Haiku 4.5 $1 per million input tokens / $5 per
million output; Sonnet 4.6 $3 / $15):

| model | input tokens | output tokens | list price |
|---|---|---|---|
| Claude Haiku 4.5 (scout, verifier, clerk) | 1,066,695 | 38,704 | $1.26 |
| Claude Sonnet 4.6 (analyst) | 267,344 | 21,722 | $1.13 |
| total, 16 runs | 1,334,039 | 60,426 | $2.39 |

So three full 20-program cycles plus the four single-program runs cost
about $2.39 of model time at list price, before credits; AgentCore,
Lambda, DynamoDB, S3 and CloudFront add fractions of a cent at this scale.
Re-run the Cost Explorer query a day or more after the runs to see the
billed figure. Dami reads the credit balance in the console; this table
does not show it.
