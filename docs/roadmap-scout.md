# Banked: FunderScout — "things you should know", per funder

Decided 2026-08-23 (Dami). Build AFTER M2+M3 land; not in the M2 scope freeze.

**What:** a fifth agent milestone. For each watched funder/program, scout the
public record (site, socials, past applicant threads) for the unwritten
things an applicant should know before spending time: payout lag reports,
T&C amendments mid-cycle, eligibility traps, disputed awards.

**Evidence bar (decided, non-negotiable): receipts only.** Every surfaced
item is a verbatim quote + source URL + date, substring-validated like every
other quote in the pipeline. The model never paraphrases claims about a
named organizer. No receipt, no item.

**Presentation (refined 2026-08-23): a summary line MAY sit on top of the
receipts, never instead of them.** The model's only prose job is
compression: each summary bullet must cite the quote ids it compresses, and
the validator enforces no-quote-no-bullet (a bullet citing nothing is
rejected back to the model, same as an invalid quote today). Item shape:
`{summary_line, quote_ids[], quotes[]}`. Summaries of raw reading — prose
first, links attached after — stay rejected: that shape ships unevidenced
claims about named funders.

**Persona fit:** Maya's version of the problem is real and already encoded
in the grants-ops playbook (T&C amendment watch, headline-vs-reachable
math, eligibility gates). A hackathon-builder flavor of the same agent is a
documented variant, not part of this repo's scope.

**Origin, for honesty in the writeup:** the author entered his first
hackathon not knowing the unwritten norms (repo-freeze-at-submission,
community policing of post-deadline commits) and paid for it. This feature
is that lesson, productized for Maya's world.
