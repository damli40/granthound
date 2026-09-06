import json
from datetime import datetime, timezone

from granthound.export import PROGRAM_FIELDS, build_export, build_stats, render_stats, verdict_flips
from granthound.pipeline.run import run_batch
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


def run_once(store, at=AT):
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    return run_batch(["p-live", "p-dead", "p-down"], at, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)


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
    assert by_id["p-down"]["verdict"] == "NEEDS_HUMAN" and by_id["p-down"]["snapshot_text"] is None
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
    assert stats["families"] == {"live": 1, "dead": 1, "suspect": 0, "unreachable": 1, "unchecked": 0}
    assert stats["quotes_stored"] > 0 and stats["programs_with_dropped_quotes"] == 0
    assert set(stats["tokens_by_node"]) == {"scout", "verifier", "analyst", "clerk"}
    assert stats["tokens_by_node"]["analyst"]["model_id"] == "fake-sonnet"
    assert stats["latest_run_id"] == data["runs"][-1]["run_id"]
    table = render_stats(data)
    assert "| Programs watched | 3 |" in table and "fake-sonnet" in table


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
