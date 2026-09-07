# Agents for Humans: the receipt boundary, or why our grant agent never writes your proposal

GrantHound decides whether a grant program is worth a small nonprofit's
time. It never drafts the proposal. That's a product boundary, and it's
also a technical one: this post is about the second kind, the code that
makes the first kind actually hold.

## The market reason

Funders discourage AI-written proposals, and the resentment toward
generic, templated "AI slop" applications runs through the audience this
product is for. Building "write my grant proposal" into this product
would put it at odds with the exact readers it needs to convince.
It would also mean competing in an already saturated, reputationally
radioactive market — plenty of tools generate proposal prose, and none of
them fix the real bottleneck for a two-person nonprofit: finding out
which funder pages are real, current, and worth the week it takes to
write anything at all. GrantHound stays on the finding-out side of that
line, on purpose, and says so out loud: it never writes your proposal. It
decides what's worth your time, and proves why.

## The design that makes the boundary real

Saying "we don't write proposals" is a sentence. Making the verdicts the
agent *does* produce trustworthy needs more than that, because a model
that quietly paraphrases or half-remembers a page is worse than no tool:
it fails exactly where a human reading the page would have caught it.

So every value that ends up in a verdict is checked in code, not taken on
the model's word:

- **Quotes are verified verbatim.** Whatever wording an agent cites as
  evidence has to appear word for word in the stored snapshot of the page
  it read. A paraphrase, a summary, or a quote from a different section
  fails the check.
- **Dates come from the scanner, not the model.** A deterministic date
  scanner reads the page first and builds the list of dates actually
  printed on it. The model can point at one of those dates; it cannot
  invent one.
- **Two strikes, then a human.** A stage gets to retry a rejected answer
  once. Fail twice and the program is flagged and routed to a human
  instead of getting an unearned APPLY or PASS.

Here is what that second failure looks like in the code that runs it —
not the Verifier's own function, but `_reject_or_accept`, the one shared
rejection helper that the Verifier, the Analyst, and the Clerk all route
their bad answers through:

```python
def _reject_or_accept(work: ProgramWork, stage: str, bad: list[tuple[str, str]]) -> str | None:
    """Count a validation failure. Returns the REJECTED message to hand back,
    or None once the stage has used up its retries (caller accepts with the
    bad parts dropped and the program flagged)."""
    count = work.rejections.get(stage, 0) + 1
    work.rejections[stage] = count
    if count >= MAX_REJECTIONS:
        work.flag(f"{stage}_quotes_unverified")
        return None
    detail = "; ".join(f"'{item}': {reason}" for item, reason in bad)
    return (
        f"REJECTED {stage}: {detail}. Copy the exact wording from the page and call again "
        f"(attempt {count} of {MAX_REJECTIONS})."
    )
```

`MAX_REJECTIONS` is 2. The model gets the rejection message back and a
chance to correct itself with the real page text in front of it; if it
still can't produce a checkable quote, the record is accepted anyway with
the unverifiable parts dropped, the program gets flagged
`verifier_quotes_unverified`, and the verdict that comes out downstream is
NEEDS_HUMAN — never an APPLY built on a quote nobody checked.

## The honest caveat

This doesn't mean every verdict is stable from one run to the next — we're
not claiming it is. All 20 watched programs now have two evaluations,
across three full cycles. Between the two latest, 3 flipped: our disclosed
fixture went NEEDS_HUMAN to APPLY after the Clerk's structured output,
which had failed to parse the cycle before, reverified cleanly; NEA Big
Read and Save The Music each went to NEEDS_HUMAN when a quote from the
Analyst, Clerk, or Verifier missed the verbatim check that cycle. None was
a change in what the page says, and the point we couldn't prove last
time is true now: every flip toward NEEDS_HUMAN has been a model
slipping, and every flip back was either the same model recovering or,
once, a page's status genuinely resolving: `lowes-hometowns` went from a
stale deadline to a confirmed-dead PASS. What the boundary
rule guarantees is narrower than "stable": a verbatim-check failure, a
date the scanner never found, or a self-contradictory timeline all route
to NEEDS_HUMAN by construction, not to an unearned APPLY or PASS.

Repo: https://github.com/damli40/granthound.
