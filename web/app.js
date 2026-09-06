/* GrantHound inbox. Renders web/data.json; composes nothing. Every line of
   text on a card is a stored field or a fixed label for a stored enum. */
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const state = { data: null, verdict: "ALL", bucket: "ALL", selected: null, tab: "read" };

  const VERDICT_LABEL = { APPLY: "APPLY", PASS: "PASS", WATCH: "WATCH", NEEDS_HUMAN: "NEEDS REVIEW", NONE: "NOT YET CHECKED" };
  const LIVENESS = {
    added: "First sight of this page",
    source_added: "Source page added",
    no_program_found: "No program found on the page",
    verified_live: "Verified live",
    reverified_live: "Re-verified live",
    verified_dead_closed: "Closed, in the funder's own words",
    verified_dead_final_call: "Final call has passed",
    verified_dead_prior_year: "Page describes a prior year's cycle",
    page_unreachable: "Page could not be fetched",
    stale_date_suspect: "Latest date on the page is in the past",
    year_trap_suspect: "A date on the page has no year. Flagged, not guessed",
    date_contradiction: "Page lists dates that contradict each other",
    changed_deadline: "A date line changed since the last snapshot",
    changed_terms: "Terms changed since the last snapshot",
    changed_new_round: "A new round is announced",
    skipped_eligibility: "Structurally ineligible",
    skipped_fit_low_score: "Fit score below the bar",
    skipped_effort_vs_award: "Effort outweighs the reachable award",
    passed_terms: "Passed on the terms",
    watch_coming_soon: "Cycle announced, not open yet"
  };
  const REASON = {
    deadline_in_future: "deadline still ahead", deadline_passed: "deadline has passed",
    prior_cycle_only: "only a prior cycle is described", next_cycle_announced: "next cycle announced",
    invitation_only: "invitation only", program_discontinued: "program discontinued",
    not_a_program_page: "not a program page", rolling_no_deadline: "rolling, no deadline", dates_unclear: "dates unclear"
  };
  const KIND = { loi: "LOI", full_application: "Full application", info_session: "Info session", award_notification: "Award notice", cycle_opens: "Cycle opens", other: "Date" };
  /* A receipt names a snapshot the export could not read. Two different
     facts arrive as snapshot_text == null: never fetched, and fetched but
     the evidence is missing from the bucket. Only the second one means a
     receipt on file cannot be checked, so it gets its own sentence. */
  const UNREADABLE = "receipt on file, not readable at export";

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
    return isNaN(d) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }
  function fmtStamp(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }) + " UTC";
  }
  function compactStamp(s) { // 20260824T001230Z -> 2026-08-24 00:12 UTC
    const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(s || "");
    return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} UTC` : (s || "");
  }
  function deadlines(p) { return (p.decision_package && p.decision_package.deadlines) || []; }
  function nextDeadline(p) {
    const future = deadlines(p).filter(d => !d.is_past).sort((a, b) => a.days_until - b.days_until);
    return future[0] || null;
  }
  function bucketOf(d) { if (!d) return null; if (d.days_until <= 30) return "30"; if (d.days_until <= 60) return "60"; if (d.days_until <= 90) return "90"; return "later"; }
  function runFor(p) { return (state.data.runs || []).find(r => r.run_id === p.run_id) || null; }
  function quotesOf(p) {
    const out = [];
    const v = p.verifier || {}; (v.evidence_quotes || []).forEach(q => out.push(q));
    const f = p.fit || {}; Object.values(f.axis_quotes || {}).forEach(q => out.push(q)); if (f.amount_quote) out.push(f.amount_quote);
    const c = p.decision_package || {}; (c.requirement_quotes || []).forEach(q => out.push(q)); (c.eligibility_quotes || []).forEach(q => out.push(q));
    return out.filter(q => typeof q === "string" && q.trim());
  }
  function shortSha(sha) { return `${esc(String(sha).slice(0, 8))}…${esc(String(sha).slice(-4))}`; }
  function whyLine(p) {
    if (!p.verdict) return "Not yet checked by a cycle.";
    const parts = [];
    const liveness = p.liveness_disposition || p.disposition;
    let head = LIVENESS[liveness] || liveness;
    if (liveness === "page_unreachable" && p.http_status) head += ` (HTTP ${p.http_status})`;
    const reason = p.verifier && REASON[p.verifier.reason];
    parts.push(reason ? `${head}: ${reason}.` : `${head}.`);
    if (p.disposition && p.disposition !== liveness && LIVENESS[p.disposition]) parts.push(`${LIVENESS[p.disposition]}.`);
    if (p.fit && p.fit.fit) parts.push(`Fit ${p.fit.fit.score}/5${p.fit.fit.capped ? " (capped: eligibility)" : ""}.`);
    if (p.verifier && p.verifier.overridden) parts.push("Model and page disagreed on liveness; sent to a human.");
    if ((p.flags || []).some(f => /quotes_unverified/.test(f))) parts.push("A quote could not be found on the page word for word; sent to a human.");
    return parts.join(" ");
  }
  function chip(verdict, extra) {
    const key = verdict || "NONE";
    return `<span class="chip ${esc(key)}${extra ? " " + extra : ""}">${esc(VERDICT_LABEL[key] || key)}</span>`;
  }

  function renderStrip() {
    const counts = { "30": 0, "60": 0, "90": 0 };
    state.data.programs.forEach(p => { const b = bucketOf(nextDeadline(p)); if (counts[b] !== undefined) counts[b]++; });
    const labels = { "30": "Due within 30 days", "60": "31 to 60 days", "90": "61 to 90 days" };
    $("#strip").innerHTML = ["30", "60", "90"].map(b =>
      `<button class="bucket" type="button" data-bucket="${b}" aria-pressed="${state.bucket === b}">${labels[b]}<span class="n">${counts[b]}</span></button>`
    ).join("") + `<button class="bucket" type="button" data-bucket="ALL" aria-pressed="${state.bucket === "ALL"}">All<span class="n">${state.data.programs.length}</span></button>`;
    $("#strip").querySelectorAll(".bucket").forEach(b => b.addEventListener("click", () => { state.bucket = b.dataset.bucket; render(); }));
  }
  function renderFilters() {
    const keys = ["ALL", "APPLY", "WATCH", "NEEDS_HUMAN", "PASS", "NONE"];
    $("#filters").innerHTML = keys.map(k =>
      `<button class="chip ${k === "ALL" ? "NONE" : esc(k)}" type="button" data-verdict="${k}" aria-pressed="${state.verdict === k}">${k === "ALL" ? "ALL" : esc(VERDICT_LABEL[k])}</button>`
    ).join("");
    $("#filters").querySelectorAll("button").forEach(b => b.addEventListener("click", () => { state.verdict = b.dataset.verdict; render(); }));
  }
  function visible() {
    return state.data.programs.filter(p => {
      const v = p.verdict || "NONE";
      if (state.verdict !== "ALL" && v !== state.verdict) return false;
      if (state.bucket !== "ALL" && bucketOf(nextDeadline(p)) !== state.bucket) return false;
      return true;
    });
  }
  function receiptLine(p) {
    const r = p.snapshot_receipt;
    if (!r) return { text: "no snapshot on file", unreadable: false };
    if (p.receipt_unreadable) return { text: `sha256 ${shortSha(r.sha256)} · ${UNREADABLE}`, unreadable: true };
    return { text: `sha256 ${shortSha(r.sha256)} · verified ${esc(compactStamp(r.fetched_at))}`, unreadable: false };
  }
  function renderCards() {
    const rows = visible();
    const cards = $("#cards");
    cards.innerHTML = rows.map(p => {
      const d = nextDeadline(p);
      const dueClass = d ? (d.days_until <= 3 ? "urgent" : d.days_until <= 14 ? "soon" : "") : "";
      const due = d ? `<span class="due ${dueClass}">${esc(KIND[d.kind] || "Date")} ${esc(fmtDate(d.iso))}${d.day_fabricated ? " (month only)" : ""} · ${d.days_until} days as of run</span>` : "";
      const collide = d && d.collides_with && d.collides_with.length ? `<span class="collide">collides with: ${esc(d.collides_with.join(", "))}</span>` : "";
      const fit = p.fit && p.fit.fit ? `<span class="fit">fit ${esc(p.fit.fit.score)} / 5${p.fit.fit.capped ? " · capped: eligibility" : ""}</span>` : "";
      const receipt = receiptLine(p);
      return `<article class="card" tabindex="0" data-id="${esc(p.program_id)}" aria-label="${esc(p.funder)}">
        <div class="top">${chip(p.verdict)}${p.is_fixture ? '<span class="chip FIXTURE">TEST FUNDER</span>' : ""}<span class="mono meta">${esc(p.source_type || "")}</span></div>
        <h3>${esc(p.funder || p.program_id)}</h3>
        <p class="why">${esc(whyLine(p))}</p>
        <div class="row">${fit}${due}${collide}</div>
        <div class="receipt${receipt.unreadable ? " unreadable" : ""}">${receipt.text} · open receipt</div>
      </article>`;
    }).join("");
    $("#quiet").hidden = rows.length > 0;
    const s = state.data.stats || {};
    $("#quiet-detail").textContent = s.latest_run_id ? `GrantHound checked ${s.programs} pages in ${s.latest_run_id}. Receipts on file.` : "No cycle has run yet.";
    cards.querySelectorAll(".card").forEach(c => {
      c.addEventListener("click", () => openDrawer(c.dataset.id));
      c.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrawer(c.dataset.id); }
        if (e.key === "ArrowDown" && c.nextElementSibling) { e.preventDefault(); c.nextElementSibling.focus(); }
        if (e.key === "ArrowUp" && c.previousElementSibling) { e.preventDefault(); c.previousElementSibling.focus(); }
      });
    });
  }

  function markQuotes(text, quotes) {
    const ranges = [];
    quotes.forEach(q => {
      const pattern = q.trim().split(/\s+/).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
      let re; try { re = new RegExp(pattern, "g"); } catch (err) { return; }
      let m; while ((m = re.exec(text)) !== null) { ranges.push([m.index, m.index + m[0].length]); if (m[0].length === 0) re.lastIndex++; }
    });
    ranges.sort((a, b) => a[0] - b[0]);
    const merged = [];
    ranges.forEach(r => { const last = merged[merged.length - 1]; if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push(r.slice()); });
    let out = "", pos = 0;
    merged.forEach(([a, b]) => { out += esc(text.slice(pos, a)) + "<mark>" + esc(text.slice(a, b)) + "</mark>"; pos = b; });
    return out + esc(text.slice(pos));
  }
  function renderDiff(text) {
    return text.split("\n").map(line => {
      const cls = line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : "";
      return `<span class="${cls}">${esc(line)}</span>`;
    }).join("\n");
  }
  function panelHtml(p) {
    if (state.tab === "read") {
      if (!p.snapshot_text) {
        const r = p.snapshot_receipt;
        if (p.receipt_unreadable && r) {
          return `<p class="unreadable">Receipt on file, not readable at export. The snapshot this verdict cites is named below, but the export could not read it back, so the quotes cannot be shown marked against it here.</p>`
            + `<div class="proof"><dl><dt>Snapshot sha256</dt><dd>${esc(r.sha256)}</dd><dt>Fetched at</dt><dd>${esc(compactStamp(r.fetched_at))}</dd><dt>Normalized snapshot key</dt><dd>${esc(r.s3_norm || "none")}</dd></dl></div>`;
        }
        return `<p>No snapshot on file for this program${p.http_status ? ` (HTTP ${esc(p.http_status)})` : ""}.</p>`;
      }
      const quotes = quotesOf(p);
      const list = quotes.length ? `<p class="meta">Quotes the verdict cites, each checked word for word against this snapshot:</p><ul class="quotes">${quotes.map(q => `<li>${esc(q)}</li>`).join("")}</ul>` : `<p class="meta">No quotes stored for this program.</p>`;
      return `${list}<pre>${markQuotes(p.snapshot_text, quotes)}</pre>`;
    }
    if (state.tab === "changed") {
      const d = p.diff_receipt;
      if (!d) return `<p>First snapshot of this page. Nothing to compare against yet.</p>`;
      const head = d.changed
        ? `<p>Changed since snapshot <span class="mono">${esc(d.old_sha256.slice(0, 8))}</span>: +${d.added_lines} / -${d.removed_lines} lines. ${d.date_lines_changed ? "A line carrying a date changed." : "No date-bearing line changed (a quiet note, not a verdict)."}</p>`
        : `<p>Identical to the previous snapshot <span class="mono">${esc(d.old_sha256.slice(0, 8))}</span>.</p>`;
      return head + (p.diff_text ? `<pre class="diff">${renderDiff(p.diff_text)}</pre>` : "");
    }
    const r = p.snapshot_receipt || {};
    const run = runFor(p);
    const models = run && run.node_models ? Object.entries(run.node_models).map(([n, m]) => `${n}: ${m}`).join("<br>") : "n/a";
    const rows = [
      ["Program", p.program_id], ["Page URL", `<a href="${esc(p.url)}" rel="noopener" target="_blank">${esc(p.url)}</a>`],
      ["Verdict", `${VERDICT_LABEL[p.verdict || "NONE"]} (${p.disposition || "n/a"})`], ["Liveness call", p.liveness_disposition || "n/a"],
      ["Deterministic call", p.deterministic_disposition || "n/a"], ["Snapshot sha256", r.sha256 || "none"],
      ["Fetched at", r.fetched_at ? compactStamp(r.fetched_at) : "n/a"], ["HTTP status", r.http_status != null ? r.http_status : (p.http_status != null ? p.http_status : "n/a")],
      ["Raw snapshot key", r.s3_raw || "none"], ["Normalized snapshot key", r.s3_norm || "none"],
      ["Evaluation row", p.eval_sk || "none"], ["Run", p.run_id || "none"], ["Run status", p.pipeline_status || "n/a"],
      ["Models billed", models], ["Flags", (p.flags || []).join(", ") || "none"], ["Fixture", p.is_fixture ? "yes: a test funder page we control, disclosed" : "no: a real funder page"]
    ];
    return `<div class="proof"><dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${k === "Page URL" || k === "Models billed" ? v : esc(v)}</dd>`).join("")}</dl></div>`;
  }
  function openDrawer(id) {
    const p = state.data.programs.find(x => x.program_id === id);
    if (!p) return;
    state.selected = id;
    $("#drawer-kicker").innerHTML = `${chip(p.verdict)} ${p.is_fixture ? '<span class="chip FIXTURE">TEST FUNDER</span>' : ""}`;
    $("#drawer-title").textContent = p.funder || p.program_id;
    $("#drawer").hidden = false; $("#scrim").hidden = false;
    renderTabs();
    $("#drawer-close").focus();
  }
  function renderTabs() {
    const p = state.data.programs.find(x => x.program_id === state.selected);
    document.querySelectorAll(".tab").forEach(t => {
      t.setAttribute("aria-selected", String(t.dataset.tab === state.tab));
      t.onclick = () => { state.tab = t.dataset.tab; renderTabs(); };
    });
    $("#panel").innerHTML = panelHtml(p);
  }
  function closeDrawer() { $("#drawer").hidden = true; $("#scrim").hidden = true; const c = document.querySelector(`.card[data-id="${CSS.escape(state.selected || "")}"]`); if (c) c.focus(); }

  function render() { renderStrip(); renderFilters(); renderCards(); }

  fetch("data.json", { cache: "no-store" }).then(r => r.json()).then(data => {
    state.data = data;
    const s = data.stats || {};
    /* The export marks a scripted test run. Say so on the page itself, so a
       screenshot of it can never be read as a live cycle. */
    $("#banner").hidden = !data.sample;
    $("#generated").textContent = `${data.org && data.org.name ? data.org.name + " · " : ""}${s.programs || 0} pages watched · latest run ${s.latest_run_id || "none"} · export ${fmtStamp(data.generated_at)}`;
    render();
  }).catch(err => { $("#cards").innerHTML = `<p class="quiet">Could not load data.json (${esc(err.message)}).</p>`; });

  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#drawer").hidden) closeDrawer(); });
})();
