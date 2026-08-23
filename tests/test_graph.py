from datetime import datetime, timezone

import pytest

from granthound.agents import tools
from granthound.agents.factories import default_executors
from granthound.agents.models import model_id_of
from granthound.config import HAIKU_MODEL_ID, SONNET_MODEL_ID, Settings
from granthound.pipeline.graph import build_graph
from granthound.pipeline.run import run_batch
from granthound.store.models import Disposition, Verdict
from tests.fakes import (
    LIVE_URL,
    ORG,
    PAGES,
    MemoryStore,
    good_analyst,
    good_clerk,
    good_scout,
    good_verifier,
    make_fetcher,
    scripted_executors,
    seeded_store,
)

AT = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def test_build_graph_requires_all_four_nodes():
    with pytest.raises(ValueError, match="clerk"):
        build_graph({"scout": object(), "verifier": object(), "analyst": object()})


def test_full_run_live_path():
    store = seeded_store()
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    summary = run_batch(["p-live", "p-dead", "p-down"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    assert summary.status == "ok" and summary.errors == []
    by_id = {o.program_id: o for o in summary.outcomes}
    assert (by_id["p-live"].verdict, by_id["p-live"].disposition) == (Verdict.APPLY, Disposition.VERIFIED_LIVE)
    assert (by_id["p-dead"].verdict, by_id["p-dead"].disposition) == (Verdict.PASS, Disposition.VERIFIED_DEAD_PRIOR_YEAR)
    assert (by_id["p-down"].verdict, by_id["p-down"].disposition) == (Verdict.NEEDS_HUMAN, Disposition.PAGE_UNREACHABLE)
    assert all(o.flags == [] for o in summary.outcomes)
    assert all(len(store.evals[pid]) == 1 for pid in by_id)
    live = store.get_last_eval("p-live")
    assert live["decision_package"]["deadlines"][0]["iso"] == "2026-09-10"
    assert live["fit"]["fit"]["score"] == 4.15 and live["verifier"]["overridden"] is False
    assert store.meta["p-live"]["verdict"] == "APPLY" and store.meta["p-live"]["latest_eval_sk"] == by_id["p-live"].eval_sk
    run = store.runs[summary.run_id]
    assert set(run["node_usage"]) == {"scout", "verifier", "analyst", "clerk"}
    assert run["node_models"] == {"scout": "fake-haiku", "verifier": "fake-haiku", "analyst": "fake-sonnet", "clerk": "fake-haiku"}
    assert run["node_usage"]["analyst"]["model_id"] == "fake-sonnet"
    assert [ex[n].calls for n in ("scout", "verifier", "analyst", "clerk")] == [1, 1, 1, 1]


def test_run_ends_after_verifier_when_nothing_is_live():
    store = seeded_store()
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    summary = run_batch(["p-dead", "p-down"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    assert summary.status == "ok"
    assert ex["analyst"].calls == 0 and ex["clerk"].calls == 0
    assert set(store.runs[summary.run_id]["node_usage"]) == {"scout", "verifier"}


def test_crash_in_analyst_still_finalizes_every_program():
    def exploding_analyst(ctx, ids):
        raise RuntimeError("bedrock is on fire")

    store = seeded_store()
    ex = scripted_executors(good_scout, good_verifier, exploding_analyst, good_clerk)
    summary = run_batch(["p-live", "p-dead"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    assert summary.status == "partial" and "RuntimeError" in summary.run_item["error"]
    live = store.get_last_eval("p-live")
    assert live["verdict"] == "NEEDS_HUMAN" and "analyst_missing" in live["flags"] and live["pipeline_status"] == "partial"
    assert store.get_last_eval("p-dead")["verdict"] == "PASS"
    assert {"scout", "verifier"} <= set(store.runs[summary.run_id]["node_usage"])


def test_model_that_never_calls_its_tool_is_flagged_not_green():
    store = seeded_store()
    ex = scripted_executors(good_scout, None, good_analyst, good_clerk)
    summary = run_batch(["p-live", "p-dead"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    assert summary.status == "ok"
    assert all(o.verdict is Verdict.NEEDS_HUMAN and "verifier_missing" in o.flags for o in summary.outcomes)
    assert store.runs[summary.run_id]["flag_counts"]["verifier_missing"] == 2


def test_unseeded_program_needs_a_url_override():
    store = MemoryStore()
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    with pytest.raises(ValueError, match="p-live"):
        run_batch(["p-live"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    summary = run_batch(["p-live"], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex,
                        url_overrides={"p-live": LIVE_URL})
    assert summary.outcomes[0].verdict is Verdict.APPLY and "meta_missing" in summary.outcomes[0].flags


def test_tool_shims_expose_the_expected_schemas():
    expected = {
        tools.fetch_and_snapshot: ["program_id"],
        tools.get_verification_brief: ["program_id"],
        tools.record_verification: ["program_id", "disposition", "reason", "evidence_quotes"],
        tools.get_analysis_brief: ["program_id"],
        tools.record_fit: [
            "program_id", "eligibility", "eligibility_quote", "explicit_funding", "explicit_funding_quote",
            "effort_to_award", "effort_to_award_quote", "strategic", "strategic_quote", "reliability", "reliability_quote",
        ],
        tools.get_decision_brief: ["program_id"],
        tools.record_decision_package: ["program_id", "deadline_isos", "deadline_kinds", "requirement_quotes", "eligibility_quotes"],
    }
    for shim, required in expected.items():
        schema = shim.tool_spec["inputSchema"]["json"]
        assert schema["required"] == required, shim.tool_name
        assert "tool_context" not in schema["properties"]
    assert set(tools.record_fit.tool_spec["inputSchema"]["json"]["properties"]) >= {"headline_amount", "reachable_amount", "amount_quote"}


def test_default_executors_build_four_agents_with_configured_models():
    settings = Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b", "AWS_REGION": "us-east-1"})
    ex = default_executors(settings)
    assert list(ex) == ["scout", "verifier", "analyst", "clerk"]
    assert model_id_of(ex["analyst"]) == SONNET_MODEL_ID
    assert all(model_id_of(ex[n]) == HAIKU_MODEL_ID for n in ("scout", "verifier", "clerk"))
    assert ex["scout"].tool_names == ["fetch_and_snapshot"]
    assert ex["verifier"].tool_names == ["get_verification_brief", "record_verification"]
    assert ex["analyst"].tool_names == ["get_analysis_brief", "record_fit"]
    assert ex["clerk"].tool_names == ["get_decision_brief", "record_decision_package"]
    assert ex["analyst"].model.config["max_tokens"] == 2500 and ex["scout"].model.config["max_tokens"] == 1500
    assert ex["scout"].model.config["temperature"] == 0
    # House rule: every boto3 client retries adaptively. The Bedrock client
    # is built inside BedrockModel, so this is the only place it is visible.
    for node in ("scout", "verifier", "analyst", "clerk"):
        assert ex[node].model.client.meta.config.retries == {"mode": "adaptive", "total_max_attempts": 5}


def test_every_prompt_declares_every_fence_label_as_data():
    """A label a prompt does not name is a fence the model has no reason to respect."""
    from granthound.agents import prompts
    from granthound.pipeline.stages import FENCE_LABELS

    for name in ("VERIFIER", "ANALYST", "CLERK"):
        text = getattr(prompts, name)
        for label in FENCE_LABELS:
            assert f"<<<{label}" in text, f"{name} does not declare the {label} fence"
