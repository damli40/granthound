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

## What a cycle does

One cycle runs four agents in a row over each funder page. The **Scout**
fetches the page and stores a hashed snapshot — that snapshot is the
receipt everything else is checked against. The **Verifier** decides whether
the program is actually live, in the funder's own words. The **Analyst**
scores fit against your org's profile. The **Clerk** collects the dates and
requirements for the programs worth your time.

The boundary rule is what makes the verdicts checkable: **every quote an
agent stores must appear, character for character, in that stored snapshot,
and every date must be one the page actually printed.** The recording tools
enforce this in code, not in the prompt. A quote that isn't on the page is
dropped rather than saved, and the program is handed to a human instead of
being scored. So any verdict can be re-derived from the snapshot it cites,
by you, later, without trusting the model that produced it.

## Run it

```bash
.venv/bin/python scripts/seed_load.py    # load your seed list into the store
.venv/bin/python scripts/run_local.py --all
```

`--program-id ID` (repeatable) runs a subset; `--no-llm --program-id ID`
runs only the deterministic fetch-and-scan half, with no model calls and no
model costs.

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
