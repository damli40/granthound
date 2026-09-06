import json
from datetime import datetime, timezone

from granthound.export import PROGRAM_FIELDS, build_export, build_stats, filter_runs_since, render_stats, verdict_flips
from granthound.pipeline.run import run_batch
from granthound.store.models import Disposition
from tests.fakes import (
    ORG,
    PAGES,
    good_analyst,
    good_clerk,
    good_scout,
    good_verifier,
    make_fetcher,
    scripted_executors,
    seeded_store,
)

AT = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)

# The distinct sentences the scripted good_* nodes quote, read off tests/fakes.py
# by hand rather than recomputed with the code under test. p-live cites the
# October date on two fit axes and the Clerk repeats two sentences the Analyst
# already used, so the ten quote SLOTS in the sample hold six distinct strings.
EXPECTED_DISTINCT_QUOTES = frozenset({
    "Applications are due October 5, 2026.",
    "Eligible applicants are 501(c)(3) organizations serving Franklin County youth.",
    "Riverbend Community Grants.",
    "Letters of intent are due September 10, 2026.",
    "Awards range from $5,000 to $25,000 per organization.",
    "Applications were due March 1, 2025.",
})


def run_once(store, at=AT):
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    return run_batch(["p-live", "p-dead", "p-down"], at, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)


def quote_slots(store, program_ids=("p-live", "p-dead", "p-down")) -> int:
    """Every quote CITATION in the latest eval of each program, duplicates included."""
    slots = 0
    for pid in program_ids:
        ev = store.get_last_eval(pid) or {}
        slots += len((ev.get("verifier") or {}).get("evidence_quotes") or [])
        slots += len((ev.get("fit") or {}).get("axis_quotes") or {})
        slots += 1 if (ev.get("fit") or {}).get("amount_quote") else 0
        package = ev.get("decision_package") or {}
        slots += len(package.get("requirement_quotes") or []) + len(package.get("eligibility_quotes") or [])
    return slots


def test_export_carries_every_program_with_its_receipt_text():
    store = seeded_store()
    store.put_program_meta({"program_id": "p-new", "url": "https://x.org/new", "funder": "New", "source_type": "test", "is_fixture": True})
    run_once(store)
    data = build_export(store, ORG, now=NOW)

    assert data["generated_at"] == NOW.isoformat()
    assert data["org"]["name"] == ORG.name and data["org"]["commitment_windows"][0]["label"] == "fall program launch"
    assert [p["program_id"] for p in data["programs"]] == ["p-dead", "p-down", "p-live", "p-new"]
    by_id = {p["program_id"]: p for p in data["programs"]}
    assert by_id["p-live"]["verdict"] == "APPLY" and "Riverbend" in by_id["p-live"]["snapshot_text"]
    assert by_id["p-live"]["fit"]["fit"]["score"] == 4.15
    assert by_id["p-live"]["eval_sk"].startswith("EVAL#2026-08-21")
    assert by_id["p-live"]["receipt_unreadable"] is False
    assert by_id["p-down"]["verdict"] == "NEEDS_HUMAN" and by_id["p-down"]["snapshot_text"] is None
    # p-down was never fetched, so there is no receipt to be unreadable. That is
    # a different fact from "the receipt exists and the object is gone".
    assert by_id["p-down"]["receipt_unreadable"] is False
    assert by_id["p-new"]["verdict"] is None and by_id["p-new"]["is_fixture"] is True
    assert all(set(PROGRAM_FIELDS) <= set(p) for p in data["programs"])
    assert len(data["runs"]) == 1 and data["runs"][0]["node_models"]["analyst"] == "fake-sonnet"
    json.dumps(data)  # must be plain JSON


def test_stats_count_verdicts_families_quotes_and_tokens():
    store = seeded_store()
    run_once(store)
    data = build_export(store, ORG, now=NOW)
    stats = data["stats"]
    assert stats["programs"] == 3
    assert stats["verdict_counts"] == {"APPLY": 1, "PASS": 1, "NEEDS_HUMAN": 1}
    assert stats["families"] == {"live": 1, "dead": 1, "suspect": 0, "unreachable": 1, "unchecked": 0, "unknown": 0}
    assert stats["quotes_stored"] > 0 and stats["programs_with_dropped_quotes"] == 0
    assert stats["receipts_unreadable"] == 0
    assert set(stats["tokens_by_node"]) == {"scout", "verifier", "analyst", "clerk"}
    assert "fake-sonnet" in stats["tokens_by_node"]["analyst"]["models"]
    assert stats["latest_run_id"] == data["runs"][-1]["run_id"]
    table = render_stats(data)
    assert "| Programs watched | 3 |" in table and "fake-sonnet" in table


def test_quotes_stored_counts_distinct_sentences_not_slots():
    store = seeded_store()
    run_once(store)
    data = build_export(store, ORG, now=NOW)

    # What the store actually holds, gathered without the code under test.
    stored = set()
    for p in data["programs"]:
        stored |= set((p.get("verifier") or {}).get("evidence_quotes") or [])
        stored |= set(((p.get("fit") or {}).get("axis_quotes") or {}).values())
        if (p.get("fit") or {}).get("amount_quote"):
            stored.add(p["fit"]["amount_quote"])
        package = p.get("decision_package") or {}
        stored |= set(package.get("requirement_quotes") or [])
        stored |= set(package.get("eligibility_quotes") or [])
    assert stored == EXPECTED_DISTINCT_QUOTES

    # The dedupe is real, not a coincidence of the fixtures: ten citations,
    # six distinct sentences. (Here the per-program sum and the union across
    # programs both come to 6, because no sentence is cited by two programs.)
    assert quote_slots(store) == 10
    assert data["stats"]["quotes_stored"] == len(EXPECTED_DISTINCT_QUOTES) == 6
    assert "| Distinct quotes stored (each verbatim-checked against its snapshot) | 6 |" in render_stats(data)


def test_quotes_are_distinct_per_program_and_survive_whitespace_differences():
    same_sentence = "Applications are due October 5, 2026."
    entry_a = {
        "program_id": "a", "verdict": "APPLY", "disposition": "verified_live", "flags": [],
        "verifier": {"evidence_quotes": [same_sentence, "Applications  are due\nOctober 5, 2026."]},
    }
    entry_b = {
        "program_id": "b", "verdict": "APPLY", "disposition": "verified_live", "flags": [],
        "verifier": {"evidence_quotes": [same_sentence]},
    }
    # Program a cites one sentence twice, spelled with different whitespace: one quote.
    assert build_stats([entry_a], [])["quotes_stored"] == 1
    # Two programs citing the same sentence is two pieces of evidence, one per
    # program -- not one. A global set would report 1 and understate the work.
    assert build_stats([entry_a, entry_b], [])["quotes_stored"] == 2


def test_tokens_by_node_keeps_each_model_separate():
    runs = [
        {
            "run_id": "r1", "at": "2026-08-21T12:00:00+00:00", "status": "ok",
            "node_usage": {"analyst": {"model_id": "sonnet-old", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
        },
        {
            "run_id": "r2", "at": "2026-08-22T12:00:00+00:00", "status": "ok",
            "node_usage": {"analyst": {"model_id": "sonnet-new", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150}},
        },
    ]
    stats = build_stats([], runs)
    analyst = stats["tokens_by_node"]["analyst"]
    assert analyst["total_tokens"] == 165 and analyst["input_tokens"] == 110 and analyst["output_tokens"] == 55
    assert analyst["runs"] == 2
    assert set(analyst["models"]) == {"sonnet-old", "sonnet-new"}
    assert analyst["models"]["sonnet-old"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "runs": 1}
    assert analyst["models"]["sonnet-new"] == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "runs": 1}
    table = render_stats({"generated_at": NOW.isoformat(), "sample": False, "stats": stats})
    assert "analyst 165 (sonnet-new 150 · sonnet-old 15)" in table


def test_a_disposition_in_no_family_is_unknown_never_live():
    entry = {
        "program_id": "p-odd",
        "verdict": "PASS",
        "disposition": Disposition.PASSED_TERMS.value,
        "liveness_disposition": Disposition.PASSED_TERMS.value,
        "snapshot_receipt": {"s3_norm": "snapshots/p-odd/x.norm.md"},
        "flags": [],
        "receipt_unreadable": False,
    }
    stats = build_stats([entry], [])
    assert stats["families"]["unknown"] == 1
    assert stats["families"]["live"] == 0
    table = render_stats({"generated_at": NOW.isoformat(), "sample": False, "stats": stats})
    assert "| Unclassified disposition (investigate) | 1 |" in table


def test_an_unreadable_receipt_is_counted_not_silently_empty():
    store = seeded_store()
    run_once(store)
    norm_key = store.get_last_eval("p-live")["snapshot_receipt"]["s3_norm"]
    del store.objects[norm_key]

    data = build_export(store, ORG, now=NOW)
    entry = {p["program_id"]: p for p in data["programs"]}["p-live"]
    assert entry["snapshot_text"] is None
    assert entry["receipt_unreadable"] is True
    assert data["stats"]["receipts_unreadable"] == 1
    assert "| Receipts on file but unreadable at export | 1 |" in render_stats(data)


def test_a_sample_export_says_so_and_a_clean_live_one_carries_no_warning_rows():
    store = seeded_store()
    run_once(store)
    sample = build_export(store, ORG, now=NOW, sample=True)
    live = build_export(store, ORG, now=NOW)
    assert sample["sample"] is True and live["sample"] is False

    sample_table = render_stats(sample)
    assert "| SAMPLE DATA (scripted test run, not a live export) | do not publish |" in sample_table

    live_table = render_stats(live)
    assert "SAMPLE DATA" not in live_table
    assert "Unclassified disposition" not in live_table
    assert "Receipts on file but unreadable" not in live_table
    assert "Source: web/data.json" in live_table
    assert "Source: /elsewhere/sample.json" in render_stats(live, source="/elsewhere/sample.json")


def test_stats_on_an_empty_store_do_not_crash():
    data = build_export(seeded_store(), ORG, now=NOW)
    assert data["stats"]["programs"] == 3 and data["stats"]["families"]["unchecked"] == 3
    assert data["stats"]["latest_run_id"] is None
    assert "| Programs watched | 3 |" in render_stats(data)


def test_verdict_flips_compare_the_two_latest_evals():
    # Second sight of p-live is suggested REVERIFIED_LIVE; the scripted
    # verifier records "verified_live", which the lattice does not allow
    # from that suggestion, so the record is overridden and the verdict
    # becomes NEEDS_HUMAN. That is a real flip, and this test wants one.
    store = seeded_store()
    run_once(store)
    run_once(store, at=datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc))
    rows = verdict_flips(store)
    by_id = {r["program_id"]: r for r in rows}
    assert [r["program_id"] for r in rows] == ["p-dead", "p-down", "p-live"]
    assert all(r["runs_compared"] == 2 for r in rows)
    assert by_id["p-dead"]["flipped"] is False and by_id["p-dead"]["previous"] == by_id["p-dead"]["latest"] == "PASS"
    assert by_id["p-down"]["flipped"] is False and by_id["p-down"]["latest"] == "NEEDS_HUMAN"
    assert by_id["p-live"]["flipped"] is True
    assert (by_id["p-live"]["previous"], by_id["p-live"]["latest"]) == ("APPLY", "NEEDS_HUMAN")


def test_filter_runs_since_keeps_the_cutoff_day_and_drops_earlier_ones():
    runs = [
        {"run_id": "old", "at": "2026-08-23T23:59:59.999999+00:00"},
        {"run_id": "midnight", "at": "2026-09-06T00:00:00.000000+00:00"},
        {"run_id": "new", "at": "2026-09-06T08:34:24.853473+00:00"},
        {"run_id": "no-at"},
    ]
    kept = filter_runs_since(runs, "2026-09-06")
    assert [r["run_id"] for r in kept] == ["midnight", "new"]


def test_filter_runs_since_feeds_build_stats_and_drops_the_excluded_models():
    runs = [
        {
            "run_id": "aug", "at": "2026-08-23T21:29:06.912362+00:00", "status": "ok",
            "node_usage": {"analyst": {"model_id": "nova-pro", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
        },
        {
            "run_id": "sep", "at": "2026-09-06T08:34:24.853473+00:00", "status": "ok",
            "node_usage": {"analyst": {"model_id": "sonnet-4-6", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150}},
        },
    ]
    kept = filter_runs_since(runs, "2026-09-06")
    stats = build_stats([], kept)
    assert stats["runs"] == 1
    assert set(stats["tokens_by_node"]["analyst"]["models"]) == {"sonnet-4-6"}
    assert stats["latest_run_id"] == "sep"
