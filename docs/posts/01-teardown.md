# Agents for Humans: we pointed a grant agent at 19 real funder pages. Here is what was stale.

GrantHound is a background agent, built for AWS's Agents for Humans
hackathon, that watches funder grant pages for small nonprofits and only
ever tells you three things: is the program actually live, do you qualify,
and what is the deadline — each claim backed by a snapshot of the exact
page it read.

Before we say anything about what the agent decides, here is what it found
when we pointed it at 19 real funder pages: community foundations,
corporate-giving programs, national funders, the kind of pages a
one-person development shop checks by hand every week. 14 of those 19 were
dead, stale, or self-contradictory. Five were live. This isn't a
hypothetical about "AI search gives you broken links" — it's what our own
agent found on pages that, to a human skimming them, mostly look fine.

## Three ways a funder page lies to you

**Dead, and still says open.** A community foundation's grants page can sit
there for months after a cycle closes, because nobody on staff owns
updating it once the deadline passes. The page still reads "currently
accepting applications." Nothing on the page tells you it's over — you'd
have to already know, or waste the week finding out.

**Stale, with no year attached.** A corporate hometown-grants program
listed a deadline as a month and a day, no year. That's not a typo; it's
how a lot of funder pages are maintained — someone edits the copy once a
year and forgets the year is load-bearing. Read today, that date could
mean this cycle or the one that already happened. A human skimming it
picks one. Our agent doesn't guess; it flags it.

**Self-contradictory.** A regional foundation's competitive-grants page
listed a deadline that only makes sense with a year attached, and the
year, on that page, doesn't resolve one way. That's the same failure mode
as above with a sharper name: a "year trap." We also treat a page whose
deadline-looking dates span more than 30 days apart as self-contradictory
on purpose — real funders sometimes lay out a multi-stage timeline (an
opens date, an early deadline, a final deadline) and we would rather flag
that as ambiguous than silently pick one for you.

## The measured numbers

Every number below is from run `run-20260906T083424Z`, part of the cycle
recorded on 2026-09-06, printed by `scripts/stats.py --since 2026-09-06` —
not typed by hand, not a sample run picked to look good. Runs made in
August, while models were still being selected, are excluded from these
counts and stay in the store for history.

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

Twenty programs watched, not nineteen, because one seed in the list is a
fixture page we control ourselves, disclosed as such, used only to
demonstrate a page *changing* on camera without waiting on a real funder
to edit their site on our schedule.

## What the agent does with a page it can't trust

Every disposition the agent can assign to a page comes from a closed set,
not free text the model invents:

```python
VERIFIED_DEAD_CLOSED = "verified_dead_closed"
VERIFIED_DEAD_FINAL_CALL = "verified_dead_final_call"
VERIFIED_DEAD_PRIOR_YEAR = "verified_dead_prior_year"
PAGE_UNREACHABLE = "page_unreachable"
STALE_DATE_SUSPECT = "stale_date_suspect"
YEAR_TRAP_SUSPECT = "year_trap_suspect"
DATE_CONTRADICTION = "date_contradiction"
```

When a page lands in one of the suspect dispositions, the agent does not
pick a side. The verdict becomes NEEDS_HUMAN — not APPLY, not PASS — and
the inbox shows exactly which quote or date triggered it, next to a link
to the funder's own live page so you can check it yourself in under a
minute. NEEDS_HUMAN is not a failure state for the product; the failure
state is a tool that guesses and calls it confidence.

The full pipeline, the disposition enum, the deadline scanner, and the
verbatim-quote checker are in the repo:
https://github.com/damli40/granthound.
