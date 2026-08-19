# GrantHound

A background agent for small nonprofits that watches funder pages, verifies
each grant program is **actually live**, scores fit against your org's
profile, tracks deadlines and rule changes, and surfaces only apply-or-pass
decisions — every verdict carrying a dated page-snapshot receipt.

GrantHound never writes your proposal. It decides what's worth your time,
and proves why.

> Built for the AWS **Agents for Humans** hackathon (Good Neighbor track)
> with the Strands Agents SDK on Amazon Bedrock AgentCore.

**Status: under construction** — quickstart, architecture diagram, and the
measured teardown table land here before submission.

## Provenance

The verification *methodology* GrantHound implements (liveness rules like
the year-check, a weighted fit rubric with a hard eligibility gate, the
disposition taxonomy, headline-vs-reachable award decomposition) is ported
from the author's own pre-existing grant-pipeline playbook — a set of
markdown process documents containing **zero code**. Every line of code in
this repository was written during the hackathon submission period.
Standard open-source dependencies are listed in `agent/requirements.txt`
and `web/package.json`.

One seed entry, `fixtures/sunset-fund`, is a **test funder page we control**
(marked `is_fixture: true` in the data and disclosed in the demo) — it
exists so a page *change* can be demonstrated on camera; real funders don't
edit their pages on your recording schedule. All other seeds are real
funder pages, and the agent's verdicts about them are recomputable live.
