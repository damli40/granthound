# Submission checklist (walked against the artifact, not from memory)

Each row records what was actually observed, with the command or page it
was observed on. Rows marked **Dami** need a person: a phone, a YouTube
login, or the Devpost account.

| Check | How | Result |
|---|---|---|
| Public repo opens logged out | incognito: https://github.com/damli40/granthound | pending: flip not yet done |
| About sidebar shows "MIT" | `gh api repos/damli40/granthound --jq .license.spdx_id` | `MIT` on the private repo (2026-09-07 01:10 WAT); re-check after the flip |
| README diagram renders | incognito, top of README | pending: flip not yet done |
| Live inbox opens | `curl -I https://d39zkv96tau3is.cloudfront.net/` | 200 text/html; data.json 200 application/json (20 programs, sample=false); deadlines.ics 200 text/calendar; fixture page 200 (2026-09-07 01:30 WAT) |
| Live inbox opens on a phone | **Dami**: open the SiteUrl on the phone, open one card, confirm the drawer scrolls and the page behind it does not | Dami |
| A receipt opens and shows marked quotes | click any card, "What we read" tab | **Dami** (checked by the implementer in Task 7 on desktop; phone unverified) |
| Fixture card is tagged TEST FUNDER | filter, look | verified in Task 8 on desktop |
| Fresh clone, quickstart, tests pass | filtered tree in a fresh venv: `pip install -r requirements-dev.txt && pytest -q tests` | 221 passed in 7.4 s (2026-09-07, filtered tree at ad316c0) |
| README local-serve step works | `cd web && python3 -m http.server 8765`, then fetch /, /styles.css, /app.js, /data.json, /deadlines.ics, /fixtures/sunset-fund/index.html | all six 200 |
| No internal files in public history | `git log --all --name-only` on the filtered clone, grep for CLAUDE.md, AGENTS.md, handoff.md, log.md, description.md, docs/superpowers, design-brief, submission-notes | empty |
| No secret in public history | `git log -p --all` grep for a Telegram bot-token shape | 0 hits |
| Video public, "Not for Kids", under 5:00 | YouTube page, logged out | **Dami**: record from `docs/video-script.md`, upload Public or Unlisted, mark Not for Kids, paste the URL into `docs/devpost.md` |
| Devpost: name, tagline, description, track Good Neighbor, Builder ID, repo, video, demo URL, 3 post URLs | Devpost edit page (project 1385909) | **Dami**: copy from `docs/devpost.md`; the entry is still "Untitled" / pre-draft |
| Devpost description reads without clicking anything | read it cold | **Dami** after pasting |
| No "Sonnet 5" anywhere public | `grep -rni "sonnet 5\|sonnet-5" --include='*.md'` on the filtered tree | empty in every .md; `web/data.json` keeps one August run row with the `sonnet-5` model id (the full-store export; README's measured section explains those runs are excluded from the table) |
| Three posts published | **Dami**: post `docs/posts/01-teardown.md`, `02-scheduling-strands-on-agentcore.md`, `03-receipt-boundary.md`; paste the URLs into Devpost | Dami |
| Credits form submitted (closed Sep 11 12pm PT) | **Dami** | Dami |
