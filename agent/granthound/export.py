"""The inbox export: everything the static page shows, from the store.

Pure over the Store protocol so the same code runs against MemoryStore in
tests and LiveStore in scripts/export_inbox.py. The page renders these
fields; it never composes claims. Every number in README, posts and the
video is read off `build_stats` (product rule 5).
"""

from collections import Counter
from datetime import date, datetime

from granthound.seeds.profile import OrgProfile
from granthound.store.models import Disposition
from granthound.store.protocol import Store
from granthound.tools.refinement import DEAD_FAMILY, LIVE_FAMILY, SUSPECT_FAMILY

EVAL_FIELDS = (
    "verdict", "disposition", "liveness_disposition", "deterministic_disposition", "pipeline_status",
    "fit", "verifier", "decision_package", "flags", "snapshot_receipt", "diff_receipt", "date_scan",
    "run_id", "fetched_at", "http_status", "is_first_eval", "error",
)
PROGRAM_FIELDS = (
    "program_id", "funder", "url", "source_type", "is_fixture", "eval_sk",
    "snapshot_text", "diff_text", "receipt_unreadable",
) + EVAL_FIELDS


def _read_text(store: Store, key: str | None) -> str | None:
    if not key:
        return None
    try:
        return store.get_text(key)
    except Exception:  # noqa: BLE001 -- a missing object must not sink the export; the page shows "not on file"
        return None


def program_entry(store: Store, meta: dict) -> dict:
    pid = meta["program_id"]
    entry = {
        "program_id": pid,
        "funder": meta.get("funder"),
        "url": meta.get("url"),
        "source_type": meta.get("source_type"),
        "is_fixture": bool(meta.get("is_fixture", False)),
        "eval_sk": None,
        "snapshot_text": None,
        "diff_text": None,
        # True only when a receipt names a snapshot we then could not read.
        # Without this, "the page was never fetched" and "the evidence is
        # missing from the bucket" both arrive as snapshot_text=None, and the
        # second one -- the one that means the receipt cannot be checked --
        # would never be counted anywhere.
        "receipt_unreadable": False,
        **{field: None for field in EVAL_FIELDS},
        "flags": [],
    }
    ev = store.get_last_eval(pid)
    if ev is None:
        return entry
    for field in EVAL_FIELDS:
        entry[field] = ev.get(field)
    entry["flags"] = list(ev.get("flags") or [])
    entry["eval_sk"] = ev.get("sk")
    receipt = ev.get("snapshot_receipt") or {}
    entry["snapshot_text"] = _read_text(store, receipt.get("s3_norm"))
    entry["receipt_unreadable"] = bool(ev.get("snapshot_receipt")) and entry["snapshot_text"] is None
    diff = ev.get("diff_receipt") or {}
    entry["diff_text"] = _read_text(store, diff.get("s3_key"))
    return entry


def _family(entry: dict) -> str:
    if entry["verdict"] is None:
        return "unchecked"
    liveness = entry.get("liveness_disposition") or entry.get("disposition")
    if liveness == Disposition.PAGE_UNREACHABLE.value:
        return "unreachable"
    if liveness in {d.value for d in LIVE_FAMILY}:
        return "live"
    if liveness in {d.value for d in DEAD_FAMILY}:
        return "dead"
    if liveness in {d.value for d in SUSPECT_FAMILY}:
        return "suspect"
    # A disposition that belongs to no family is something this code has never
    # seen. Guessing "live" here would quietly add it to the headline count of
    # verified-live programs -- the one number a funder-facing page must not
    # overstate. Say so instead, and let the table ask for an investigation.
    return "unknown"


FAMILY_NAMES = ("live", "dead", "suspect", "unreachable", "unchecked", "unknown")


def _normalize_quote(text: str) -> str:
    """Collapse whitespace so the same sentence counts once however it was stored."""
    return " ".join(text.split())


def _quote_texts(entry: dict) -> tuple[set[str], bool]:
    """The DISTINCT quotes stored for one program, plus whether any were dropped.

    Counting slots overstates the evidence: two fit axes routinely cite the
    same sentence, and the Clerk repeats quotes the Analyst already used. The
    number worth publishing is how many distinct sentences were checked
    verbatim against the snapshot, not how many times they were cited.
    """
    quotes: list[str] = []
    dropped = False
    verifier = entry.get("verifier") or {}
    quotes += list(verifier.get("evidence_quotes") or [])
    dropped = dropped or bool(verifier.get("quotes_unverified"))
    fit = entry.get("fit") or {}
    quotes += list((fit.get("axis_quotes") or {}).values())
    if fit.get("amount_quote"):
        quotes.append(fit["amount_quote"])
    dropped = dropped or bool(fit.get("quotes_unverified"))
    package = entry.get("decision_package") or {}
    quotes += list(package.get("requirement_quotes") or [])
    quotes += list(package.get("eligibility_quotes") or [])
    dropped = dropped or bool(package.get("quotes_unverified"))
    return {_normalize_quote(q) for q in quotes if q}, dropped


def build_stats(programs: list[dict], runs: list[dict]) -> dict:
    verdicts = Counter(p["verdict"] for p in programs if p["verdict"])
    dispositions = Counter(p["disposition"] for p in programs if p["disposition"])
    flags = Counter(flag for p in programs for flag in p["flags"])
    families = Counter(_family(p) for p in programs)
    quotes_stored = 0
    dropped_programs = 0
    receipts_unreadable = 0
    for p in programs:
        quotes, dropped = _quote_texts(p)
        quotes_stored += len(quotes)
        dropped_programs += 1 if dropped else 0
        receipts_unreadable += 1 if p.get("receipt_unreadable") else 0
    tokens: dict[str, dict] = {}
    for run in runs:
        for node, usage in (run.get("node_usage") or {}).items():
            counts = (
                int(usage.get("input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
                int(usage.get("total_tokens") or 0),
            )
            slot = tokens.setdefault(node, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "runs": 0, "models": {}})
            # Tokens are kept per model, not just per node. A node whose model
            # was swapped between runs would otherwise show one lifetime total
            # under whichever model id happened to be newest -- a cost figure
            # attributed to a model that never billed most of it.
            per_model = slot["models"].setdefault(
                usage.get("model_id") or "n/a", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "runs": 0}
            )
            for bucket in (slot, per_model):
                bucket["input_tokens"] += counts[0]
                bucket["output_tokens"] += counts[1]
                bucket["total_tokens"] += counts[2]
                bucket["runs"] += 1
    latest = runs[-1] if runs else None
    return {
        "programs": len(programs),
        "verdict_counts": dict(verdicts),
        "disposition_counts": dict(dispositions),
        "flag_counts": dict(flags),
        "families": {name: families.get(name, 0) for name in FAMILY_NAMES},
        "quotes_stored": quotes_stored,
        "programs_with_dropped_quotes": dropped_programs,
        "receipts_unreadable": receipts_unreadable,
        "tokens_by_node": tokens,
        "runs": len(runs),
        "latest_run_id": latest["run_id"] if latest else None,
        "latest_run_at": latest["at"] if latest else None,
        "latest_run_status": latest["status"] if latest else None,
    }


def filter_runs_since(runs: list[dict], iso_date: str) -> list[dict]:
    """Runs whose `at` timestamp is on or after `iso_date` (a UTC calendar
    day, e.g. "2026-09-06").

    Used to recompute `build_stats`'s run-count and per-model token rows
    over a recent slice -- a model swap mid-project (say, from a model
    still being evaluated to the one actually shipped) otherwise stays
    mixed into a lifetime total forever, in a token figure no future run
    will ever add to again. This never touches `programs`: a program's
    verdict/disposition/quote counts come from its latest eval regardless
    of which runs are in scope here, and the live export this reads from
    is left alone -- only the printed table changes.

    A run's `at` is a full ISO 8601 timestamp with a UTC offset (e.g.
    "2026-08-23T21:28:44.152252+00:00"); comparing it lexically against
    the date's own midnight, in the same zero-padded ISO 8601 shape, gives
    the same order as comparing the parsed datetimes -- so no date-parsing
    library is needed for the comparison itself.

    Raises `ValueError` if `iso_date` is not a real calendar date in
    "YYYY-MM-DD" form -- a silent empty slice from a typo'd flag would
    otherwise print a technically-truthful table ("0 of 18 runs") for the
    wrong reason, with nothing on the page saying the date itself was bad.
    """
    date.fromisoformat(iso_date)
    cutoff = f"{iso_date}T00:00:00"
    return [r for r in runs if (r.get("at") or "") >= cutoff]


def build_export(store: Store, org: OrgProfile, *, now: datetime, sample: bool = False) -> dict:
    """The whole data file. `sample=True` marks an export built from the
    scripted test fixtures, so nothing downstream can mistake it for a live
    one and publish its numbers."""
    programs = sorted((program_entry(store, meta) for meta in store.list_programs()), key=lambda p: p["program_id"])
    runs = sorted(store.list_runs(), key=lambda r: (r.get("at") or "", r.get("run_id") or ""))
    return {
        "generated_at": now.isoformat(),
        "sample": sample,
        "org": org.model_dump(mode="json"),
        "programs": programs,
        "runs": runs,
        "stats": build_stats(programs, runs),
    }


def _render_node_tokens(node: str, usage: dict) -> str:
    models = " · ".join(
        f"{model} {counts['total_tokens']:,}" for model, counts in sorted(usage["models"].items())
    ) or "no model recorded"
    return f"{node} {usage['total_tokens']:,} ({models})"


def render_stats(data: dict, source: str = "web/data.json") -> str:
    """The measured table. Every key it reads is required, not `.get`-ed: an
    export from before a field existed must fail loudly here rather than print
    a table that silently omits a warning row."""
    s = data["stats"]
    fam = s["families"]
    verdicts = " · ".join(f"{k} {v}" for k, v in sorted(s["verdict_counts"].items())) or "none yet"
    tokens = " · ".join(
        _render_node_tokens(node, u) for node, u in sorted(s["tokens_by_node"].items())
    ) or "none yet"
    latest = f"{s['latest_run_id']} at {s['latest_run_at']} ({s['latest_run_status']})" if s["latest_run_id"] else "none yet"
    rows = []
    if data["sample"]:
        rows.append(("SAMPLE DATA (scripted test run, not a live export)", "do not publish"))
    rows += [
        ("Programs watched", s["programs"]),
        ("Latest run", latest),
        ("Runs on record", s["runs"]),
        ("Verdicts", verdicts),
        ("Verified live", fam["live"]),
        ("Verified dead (closed, final call, prior year, no program found)", fam["dead"]),
        ("Suspect (stale date, year trap, contradiction)", fam["suspect"]),
        ("Unreachable", fam["unreachable"]),
        ("Not yet checked", fam["unchecked"]),
    ]
    # The two warning rows appear only when there is something to warn about,
    # so a clean table is not padded with zeroes a reader learns to skip.
    if fam["unknown"]:
        rows.append(("Unclassified disposition (investigate)", fam["unknown"]))
    rows += [
        ("Distinct quotes stored (each verbatim-checked against its snapshot)", s["quotes_stored"]),
        ("Programs where a quote had to be dropped", s["programs_with_dropped_quotes"]),
    ]
    if s["receipts_unreadable"]:
        rows.append(("Receipts on file but unreadable at export", s["receipts_unreadable"]))
    rows.append(("Tokens by node (model)", tokens))
    lines = ["| Measure | Value |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    lines.append(f"\nGenerated {data['generated_at']} by scripts/stats.py. Source: {source}")
    return "\n".join(lines)


def verdict_flips(store: Store) -> list[dict]:
    """For each program, the verdicts of its two latest evals and whether they differ."""
    rows = []
    for meta in sorted(store.list_programs(), key=lambda m: m["program_id"]):
        evals = store.list_evals(meta["program_id"])
        latest = evals[-1] if evals else None
        previous = evals[-2] if len(evals) > 1 else None
        rows.append({
            "program_id": meta["program_id"],
            "runs_compared": min(len(evals), 2),
            "previous": previous.get("verdict") if previous else None,
            "latest": latest.get("verdict") if latest else None,
            "previous_disposition": previous.get("disposition") if previous else None,
            "latest_disposition": latest.get("disposition") if latest else None,
            "flipped": bool(previous and latest and previous.get("verdict") != latest.get("verdict")),
        })
    return rows
