# Agents for Humans: we pointed a grant agent at 19 real funder pages. Here is what was stale.

GrantHound is a background agent, built for AWS's Agents for Humans
hackathon, that watches funder grant pages and tells you three things: is
the program live, do you qualify, and when is it due — each claim backed
by a snapshot of the page it read.

Before we say anything about what the agent decides, here is what it
found. We pointed GrantHound at 19 real funder pages. 14 were dead,
stale, unfindable, or self-contradictory. Four were live, and one page
would not load at all. The pages were community foundations,
corporate-giving programs, and national funders — pages a one-person
shop checks by hand every week. This isn't a hypothetical about "AI
search gives you broken links" — it's what our own agent found on pages
that, to a human skimming them, mostly look fine.

## Four ways a funder page goes wrong

**Dead, and still says open.** A community foundation's grants page can
sit there for months after a cycle closes, because nobody owns updating
it once the deadline passes. The page still reads "currently accepting
applications." Nothing tells you it's over — you'd have to already know,
or waste the week finding out.

**Stale, with no year attached.** A corporate hometown-grants program
listed a deadline as a month and a day, no year. That's not a typo; a lot
of funder pages get edited once a year, and the year is the part that
gets forgotten. Read today, that date could mean this cycle or the one
that already happened. A human skimming it picks one. Our agent doesn't
guess; it flags it.

**Self-contradictory.** A regional foundation's competitive-grants page
listed a deadline that only makes sense with a year attached, and the
year doesn't resolve one way — the sharper name for this is a "year
trap." We also treat a page whose deadline-looking dates span more than
30 days apart as self-contradictory on purpose: real funders sometimes
lay out a multi-stage timeline months apart, and we'd rather flag that as
ambiguous than silently pick one for you.

**Unfindable.** Three of the fourteen weren't a bad date at all — the
agent read the whole page and there was no grant program on it any more.
A foundation's site can stay up while the grants page it once hosted is
gone or folded into something else. The agent doesn't invent a program to
fill that gap. It says the page has no program on it any more, instead of
guessing.

## The measured numbers

Every number below is from run `run-20260906T083424Z`, printed by
`scripts/stats.py --since 2026-09-06` — not typed by hand. Runs made in
August, while models were still being selected, are excluded and stay in
the store for history.

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
| Distinct quotes stored (each verbatim-checked against its snapshot) | 72 |
| Programs where a quote had to be dropped | 5 |

Twenty watched, not nineteen: one seed is a disclosed fixture page we
control, used only to demonstrate a page *changing* on camera without
waiting on a real funder to edit their site for us.

## What the agent does with a page it can't trust

Every disposition the agent can assign comes from a closed set, not free
text the model invents. Here's the half of that set that means you cannot
trust the page — the pipeline also has a live half (`verified_live`,
`watch_coming_soon`, and others) for pages that check out:

```python
VERIFIED_DEAD_CLOSED = "verified_dead_closed"
VERIFIED_DEAD_FINAL_CALL = "verified_dead_final_call"
VERIFIED_DEAD_PRIOR_YEAR = "verified_dead_prior_year"
NO_PROGRAM_FOUND = "no_program_found"
PAGE_UNREACHABLE = "page_unreachable"
STALE_DATE_SUSPECT = "stale_date_suspect"
YEAR_TRAP_SUSPECT = "year_trap_suspect"
DATE_CONTRADICTION = "date_contradiction"
```

When a page lands in one of the suspect dispositions, the agent doesn't
pick a side. The verdict becomes NEEDS_HUMAN — not APPLY, not PASS — and
the inbox shows
exactly which quote or date triggered it, next to a link to the funder's
own live page so you can check it yourself in under a minute. NEEDS_HUMAN
isn't a failure state for the product; the failure state is a tool that
guesses and calls it confidence.

The full pipeline, the disposition enum, the deadline scanner, and the
verbatim-quote checker are in the repo:
https://github.com/damli40/granthound.
