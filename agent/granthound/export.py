"""The inbox export: everything the static page shows, from the store.

Pure over the Store protocol so the same code runs against MemoryStore in
tests and LiveStore in scripts/export_inbox.py. The page renders these
fields; it never composes claims. Every number in README, posts and the
video is read off `build_stats` (product rule 5).
"""

from collections import Counter
from datetime import datetime

from granthound.seeds.profile import OrgProfile
from granthound.store.models import Disposition
from granthound.store.protocol import Store
from granthound.tools.refinement import DEAD_FAMILY, LIVE_FAMILY, SUSPECT_FAMILY

EVAL_FIELDS = (
    "verdict", "disposition", "liveness_disposition", "deterministic_disposition", "pipeline_status",
    "fit", "verifier", "decision_package", "flags", "snapshot_receipt", "diff_receipt", "date_scan",
    "run_id", "fetched_at", "http_status", "is_first_eval", "error",
)
PROGRAM_FIELDS = ("program_id", "funder", "url", "source_type", "is_fixture", "eval_sk", "snapshot_text", "diff_text") + EVAL_FIELDS


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
    return "unreachable" if entry.get("snapshot_receipt") is None else "live"


def _quote_counts(entry: dict) -> tuple[int, bool]:
    stored = 0
    dropped = False
    verifier = entry.get("verifier") or {}
    stored += len(verifier.get("evidence_quotes") or [])
    dropped = dropped or bool(verifier.get("quotes_unverified"))
    fit = entry.get("fit") or {}
    stored += len(fit.get("axis_quotes") or {})
    stored += 1 if fit.get("amount_quote") else 0
    dropped = dropped or bool(fit.get("quotes_unverified"))
    package = entry.get("decision_package") or {}
    stored += len(package.get("requirement_quotes") or []) + len(package.get("eligibility_quotes") or [])
    dropped = dropped or bool(package.get("quotes_unverified"))
    return stored, dropped


def build_stats(programs: list[dict], runs: list[dict]) -> dict:
    verdicts = Counter(p["verdict"] for p in programs if p["verdict"])
    dispositions = Counter(p["disposition"] for p in programs if p["disposition"])
    flags = Counter(flag for p in programs for flag in p["flags"])
    families = Counter(_family(p) for p in programs)
    quotes_stored = 0
    dropped_programs = 0
    for p in programs:
        stored, dropped = _quote_counts(p)
        quotes_stored += stored
        dropped_programs += 1 if dropped else 0
    tokens: dict[str, dict] = {}
    for run in runs:
        for node, usage in (run.get("node_usage") or {}).items():
            slot = tokens.setdefault(node, {"model_id": None, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "runs": 0})
            slot["model_id"] = usage.get("model_id") or slot["model_id"]
            slot["input_tokens"] += int(usage.get("input_tokens") or 0)
            slot["output_tokens"] += int(usage.get("output_tokens") or 0)
            slot["total_tokens"] += int(usage.get("total_tokens") or 0)
            slot["runs"] += 1
    latest = runs[-1] if runs else None
    return {
        "programs": len(programs),
        "verdict_counts": dict(verdicts),
        "disposition_counts": dict(dispositions),
        "flag_counts": dict(flags),
        "families": {name: families.get(name, 0) for name in ("live", "dead", "suspect", "unreachable", "unchecked")},
        "quotes_stored": quotes_stored,
        "programs_with_dropped_quotes": dropped_programs,
        "tokens_by_node": tokens,
        "runs": len(runs),
        "latest_run_id": latest["run_id"] if latest else None,
        "latest_run_at": latest["at"] if latest else None,
        "latest_run_status": latest["status"] if latest else None,
    }


def build_export(store: Store, org: OrgProfile, *, now: datetime) -> dict:
    programs = sorted((program_entry(store, meta) for meta in store.list_programs()), key=lambda p: p["program_id"])
    runs = sorted(store.list_runs(), key=lambda r: (r.get("at") or "", r.get("run_id") or ""))
    return {
        "generated_at": now.isoformat(),
        "org": org.model_dump(mode="json"),
        "programs": programs,
        "runs": runs,
        "stats": build_stats(programs, runs),
    }


def render_stats(data: dict) -> str:
    s = data["stats"]
    fam = s["families"]
    verdicts = " · ".join(f"{k} {v}" for k, v in sorted(s["verdict_counts"].items())) or "none yet"
    tokens = " · ".join(
        f"{node} {u['total_tokens']:,} ({u['model_id'] or 'n/a'})" for node, u in sorted(s["tokens_by_node"].items())
    ) or "none yet"
    latest = f"{s['latest_run_id']} at {s['latest_run_at']} ({s['latest_run_status']})" if s["latest_run_id"] else "none yet"
    rows = [
        ("Programs watched", s["programs"]),
        ("Latest run", latest),
        ("Runs on record", s["runs"]),
        ("Verdicts", verdicts),
        ("Verified live", fam["live"]),
        ("Verified dead (closed, final call, prior year)", fam["dead"]),
        ("Suspect (stale date, year trap, contradiction)", fam["suspect"]),
        ("Unreachable", fam["unreachable"]),
        ("Not yet checked", fam["unchecked"]),
        ("Quotes stored (each verbatim-checked against its snapshot)", s["quotes_stored"]),
        ("Programs where a quote had to be dropped", s["programs_with_dropped_quotes"]),
        ("Tokens by node (model)", tokens),
    ]
    lines = ["| Measure | Value |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    lines.append(f"\nGenerated {data['generated_at']} by scripts/stats.py over web/data.json.")
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
