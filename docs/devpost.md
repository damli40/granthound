# GrantHound — Devpost submission text

**Project name:** GrantHound
**Tagline (max 60 chars):** Verified grant decisions for small nonprofits, with receipts
**Built with:** Strands Agents SDK, Amazon Bedrock AgentCore Runtime, Amazon Bedrock (Claude Haiku 4.5, Claude Sonnet 4.6), EventBridge Scheduler, Lambda, DynamoDB, S3, CloudFront, SSM Parameter Store, AWS CDK, Python; Telegram Bot API.

This page is written to stand on its own. If you read nothing else, this is
the project.

## What is the problem, why does it matter, who is it for, how does it work

Small nonprofits find grants by refreshing funder pages by hand, over and
over, hoping to catch a cycle before it closes. The best free grant
database in America is a desktop at the county library, one day a month,
in person. Paid databases start at $299 a month, more than a month of
program budget for an organization running on $185,000 a year. AI search
tools hand back expired links and grants that do not exist — a sales pitch
dressed as research. The costliest failure here is not a rejected
proposal; it is the week spent writing to a funder whose cycle closed last
year and whose page still says "Applications open," because nothing told
the person reading it otherwise.

It matters because of who is on the other end of that wasted week. 88% of
US nonprofits spend under $500K a year. Very small nonprofits are 60% of
organizations and received 0.4% of foundation funding 2019 to 2023. These
are not organizations with a grants team and a subscription budget; they
are one or two people doing this alongside everything else the
organization needs. For them a missed deadline is a missed year, not a
missed quarter, because the next cycle for that funder may not open again
for twelve months.

The person we built this for is Maya, executive director of a $185K
community youth organization in Columbus, Ohio, with two part-time staff
and no development director. Grant-seeking is her fourth job, worked in
whatever hours are left after programs, payroll, and everything else. Her
current tools are a spreadsheet of funders, a handful of newsletters, and
that county-library terminal once a month. She does not want a draft. She
wants: "these three are real, open, and you qualify. Start with this one."

GrantHound is a background agent that watches a curated list of funder
pages, verifies each program is actually live on the funder's own words,
scores fit against the org's profile, tracks deadlines and rule changes,
and surfaces only apply-or-pass decisions — every verdict carrying a dated
page-snapshot receipt, so the claim can be checked against the page it
came from without asking anyone to just be believed. **GrantHound never
writes your proposal.** It decides what is worth your time, and proves
why. One cycle runs four Strands agents in a row over each funder page —
Scout fetches and snapshots, Verifier checks liveness, Analyst scores fit,
Clerk collects dates and requirements — and every value in the resulting
verdict traces back to a quote or a date the funder's own page printed,
not to the model's word for it. It runs on a schedule, unattended; nobody
has to remember to open a laptop and check.

## Measured, not asserted

Numbers below cover runs from 2026-09-06, the current model configuration,
run `run-20260906T114140Z`; August runs, made while models were being
selected, used Amazon Nova and remain in the store for history but are
excluded here. They are the ones a fresh `scripts/stats.py --since
2026-09-06` prints right now, not a copy kept up by hand.

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

Verdict stability so far: 20 programs with two evals; 2 verdict flip(s), now
that the unattended schedule has run twice over the full seed list. One
flip is the disclosed fixture page, changed on purpose to demonstrate a
live edit on camera — expected, not a finding. The other is real: a
stale, no-year deadline the agent had flagged NEEDS_HUMAN resolved, on
the second pass, to a confirmed dead program. Stability compares each
program's two latest evaluations across all runs in the store, not only
the runs in the table above.

## The agents

| Agent | Model | Does |
|---|---|---|
| Scout | Claude Haiku 4.5 | fetches the page, stores a hashed snapshot (the receipt everything else is checked against) |
| Verifier | Claude Haiku 4.5 | decides whether the program is live, in the funder's own words |
| Analyst | Claude Sonnet 4.6 | scores fit on five weighted axes with a hard eligibility gate |
| Clerk | Claude Haiku 4.5 | collects the dates and requirements for programs worth a human's time |

## AWS services and the Strands Agents SDK

- **Strands Agents SDK** (`GraphBuilder`): the four agents are graph nodes with one conditional edge (Verifier to Analyst fires only when something is live). Each node has one read tool and one record tool; the record tool validates in code and rejects bad values back to the model.
- **Amazon Bedrock AgentCore Runtime**: the graph is deployed as a CodeZip runtime (`agent/`). One invocation runs one cycle inside an AgentCore async task, so the runtime stays healthy-busy until the last chunk is finalized. AgentCore Observability traces show the four nodes and every tool call.
- **Amazon Bedrock**: Claude Haiku 4.5 and Claude Sonnet 4.6 via global inference profiles, `temperature=0`, explicit `max_tokens`, adaptive retries.
- **EventBridge Scheduler + Lambda**: a 12-hour schedule fires a 30-line Lambda that calls `InvokeAgentRuntime`.
- **DynamoDB + S3**: one append-only EVAL row per program per run; raw and normalized snapshots and diffs in a private bucket.
- **S3 + CloudFront**: the static inbox, regenerated from the store by `scripts/export_inbox.py`.
- **SSM Parameter Store**: holds the Telegram bot token as a SecureString; the runtime posts a cycle summary and never fails a cycle over it.

## The boundary rule

**The boundary rule** makes the verdicts checkable: every quote an agent
stores must appear word for word in the stored snapshot, and every date must
be one the page printed (a month-only date keeps its day marked as invented
and counts to month end). The recording tools enforce this in code, not in
the prompt. A quote that is not on the page is dropped, the program is
flagged, and it goes to a human instead of being acted on. Any verdict can be
re-derived from the snapshot it cites, by you, later, without trusting the
model that produced it.

## Provenance

The verification *methodology* (the year-check, a weighted fit rubric with a
hard eligibility gate, the disposition taxonomy, headline-vs-reachable award
decomposition) is ported from the author's own pre-existing grant-pipeline
playbook: markdown process documents containing **zero code**. Every line of
code in this repository was written during the hackathon submission period.
Dependencies are listed in `agent/requirements.txt` and
`requirements-dev.txt`.

One seed, `fixtures/sunset-fund`, is a **test funder page we control**
(`is_fixture: true`, hosted at
`https://d39zkv96tau3is.cloudfront.net/fixtures/sunset-fund/index.html`), so
a page *change* can be demonstrated on camera; real funders do not edit
their pages on a recording schedule. Every other seed is a real funder page,
and the agent's verdicts about them are recomputable live.

## Links, track, and posts

- **Live inbox:** https://d39zkv96tau3is.cloudfront.net
- **Repo:** https://github.com/damli40/granthound
- **Video:** VIDEO URL AT SUBMISSION
- **Track:** Good Neighbor

Three companion posts on builder.aws, written for a builder audience:

1. Agents for Humans: we pointed a grant agent at 19 real funder pages. Here is what was stale.
2. Agents for Humans: scheduling a Strands graph on AgentCore, the EventBridge to Lambda to InvokeAgentRuntime pattern.
3. Agents for Humans: the receipt boundary, or why our grant agent never writes your proposal.
