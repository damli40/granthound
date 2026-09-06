# GrantHound — 5-minute video script

Async-judged: the video and the Devpost text carry everything, so nothing
here assumes a judge also opens the repo. Target pace 130–140 words per
minute; narration budget 650–700 words for a 5:00 video.

## Narration

**0:00** (cold open, no greeting, over the measured table on screen) — We
pointed GrantHound at 19 real funder pages. 14 were dead, stale, or
self-contradictory. Five were live. This is what happened when we actually
checked, instead of trusting the page.

**0:20** (cut to a photo of a library reference desk, then to Maya's
persona card) — The best free grant database in America is a desktop at
the county library, one day a month, in person. Maya runs a
$185,000-a-year youth organization in Columbus, Ohio, with two part-time
staff and no development director, and grant-seeking is her fourth job.
She doesn't want a draft — she wants three programs that are real, open,
and a fit, and which one to start with.

**0:45** (to camera, no slide) — GrantHound never writes your proposal. It
decides what is worth your time, and proves why.

**1:10** (over `docs/architecture.svg`) — Four Strands agents run in a
graph, one after another, with one conditional edge: Verifier only hands
off to Analyst when something is actually live. The whole graph runs
inside Amazon Bedrock AgentCore Runtime, on a 12-hour EventBridge
schedule. Scout, Verifier and Clerk run on Claude Haiku 4.5. The Analyst
runs on Claude Sonnet 4.6.

**1:40** (screen: the live inbox, filtered to NEEDS REVIEW) — This is the
live inbox. I filter to NEEDS REVIEW and read one why-line out loud, in
the agent's own words, not mine. Here's the calendar link — every deadline
here is a date the funder's page printed. And here's a Telegram message on
my phone — this is what a cycle looks like when you are not at your desk.

**2:10** (a real program's receipt, "What we read" tab, then split screen
with the funder's live page) — Here's a real catch. A community
foundation's grants page reads like it's still open. I open its receipt
and click "What we read." The highlighted line is the exact wording the
page printed into the snapshot — not summarized, not guessed. Next to it,
the funder's own live page, side by side. Same page, a date with no year
attached, or a deadline the page contradicts somewhere else on itself.
GrantHound doesn't decide that's fine. It flags it, and a human decides.

**2:50** (terminal: `aws lambda invoke`, then AgentCore trace view, then
the refreshed inbox row) — Did I hardcode any of this? Watch. I run one
command in a terminal — an `aws lambda invoke` against this program's id —
and fire a real cycle on the live runtime. Cut to AgentCore's own trace
view: Scout, then Verifier, then Analyst, then Clerk, each one a real
model call, each one logged. When it finishes, I run `export_inbox.py` and
reload the page. Same program, a new timestamp, a new hash on the
snapshot. Nothing on this screen was typed by hand between those two
reloads — the row changed because the agent ran.

**3:40** (the fixture page, then a deploy command, then the inbox row) —
This one is a test page we control. Real funders don't edit their pages
on my recording schedule. It's our own fixture, disclosed in the repo, so
a real change can happen on camera instead of asking you to trust a
screenshot. I edit its deadline, redeploy the page, and let the next check
run. The inbox reports it plainly: changed_deadline. Same pipeline, same
boundary rule, same receipt — the only difference is that I own this page,
and I just told you so.

**4:20** (the boundary-rule line from `docs/architecture.mmd`, on screen,
said in one breath) — Every quote must appear word for word in the
snapshot. Every date must be one the page printed. Fail twice and the
program goes to a human. A model that paraphrases cannot reach APPLY.

**4:45** (back on the live inbox, then the end slide) — For organizations
where a missed deadline is a missed year. Onboarding by Telegram or a web
form is next — not built yet; today you edit one file. The live inbox, the
repo, and this page on Devpost are on screen now.

## Shot list

| Timestamp | On screen | Source | Lower-third label |
|---|---|---|---|
| 0:00 | The measured table, full screen | `docs/measured.md` (rendered) | 19 pages, checked, not trusted |
| 0:20 | Library reference-desk photo, then Maya persona card | `docs/superpowers/SPEC.md` persona facts | Who this is for |
| 0:45 | Presenter to camera, plain background | — | The one thing this agent will not do |
| 1:10 | Architecture diagram | `docs/architecture.svg` | Four agents, one pipeline |
| 1:40 | Live inbox, filtered to NEEDS REVIEW; calendar tab; phone with Telegram message | `https://d39zkv96tau3is.cloudfront.net` | Clerk's decision, in your inbox |
| 2:10 | Receipt "What we read" tab; split screen with funder's live page | live inbox + the real funder's page | Step 2 of 4: verifying dates against the live page |
| 2:50 | Terminal running `aws lambda invoke`; AgentCore trace view; refreshed inbox row | live AWS console / CLI | Step 1 of 4 through Step 4 of 4: Scout, Verifier, Analyst, Clerk |
| 3:40 | Fixture page before/after edit; deploy command; inbox row showing `changed_deadline` | `https://d39zkv96tau3is.cloudfront.net/fixtures/sunset-fund/index.html` | Disclosed: this page is ours |
| 4:20 | Boundary-rule text card | `docs/architecture.mmd` rule box | The rule everything else depends on |
| 4:45 | Live inbox, then end slide with three links | live inbox + end card | Live inbox · Repo · Devpost |

## Recording notes

- Record twice: a full take, then a backup take, and cut from whichever
  one lands the timing.
- Upload to YouTube set to **"Not for Kids"**, and **Public or Unlisted**
  — never Private, or the Devpost embed will not load for judges.
- Export at 1080p.
- Terminal font at 18pt for the `aws lambda invoke` and trace shots, so
  the command and program id are readable at video scale.
