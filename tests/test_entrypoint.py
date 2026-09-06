import os
from pathlib import Path

import pytest

from granthound.entrypoint import CHUNK_SIZE, PayloadError, chunk, load_runtime_env, parse_payload

KNOWN = lambda: ["p-c", "p-a", "p-b"]  # noqa: E731


def test_explicit_ids_are_sorted_and_returned():
    assert parse_payload({"program_ids": ["p-b", "p-a"]}, KNOWN) == ["p-a", "p-b"]


def test_cycle_mode_lists_every_known_program_sorted():
    assert parse_payload({"mode": "cycle"}, KNOWN) == ["p-a", "p-b", "p-c"]


def test_cycle_mode_limit_takes_the_first_n():
    assert parse_payload({"mode": "cycle", "limit": 2}, KNOWN) == ["p-a", "p-b"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"program_ids": ["a"], "mode": "cycle"},
        {"program_ids": []},
        {"program_ids": ["a", "a"]},
        {"program_ids": "a"},
        {"mode": "nightly"},
        {"mode": "cycle", "limit": 0},
        {"mode": "cycle", "limit": True},
        {"mode": "cycle", "limt": 3},
        {"program_ids": ["a"], "limit": 2},
        "just a string",
    ],
)
def test_bad_payloads_are_refused(payload):
    with pytest.raises(PayloadError):
        parse_payload(payload, KNOWN)


def test_chunks_are_five_wide_and_keep_order():
    ids = [f"p-{i:02d}" for i in range(12)]
    parts = chunk(ids)
    assert CHUNK_SIZE == 5
    assert [len(p) for p in parts] == [5, 5, 2]
    assert [pid for part in parts for pid in part] == ids
    assert chunk([]) == []


def test_runtime_env_sets_only_what_is_missing(tmp_path):
    env_file = tmp_path / "runtime.env"
    env_file.write_text("# comment\nGRANTHOUND_TABLE=t-from-file\nAWS_REGION = us-east-1 \nBROKEN LINE\n")
    environ = {"AWS_REGION": "eu-west-1"}
    applied = load_runtime_env(env_file, environ)
    assert applied == {"GRANTHOUND_TABLE": "t-from-file"}
    assert environ == {"AWS_REGION": "eu-west-1", "GRANTHOUND_TABLE": "t-from-file"}


def test_runtime_env_missing_file_is_a_noop(tmp_path):
    assert load_runtime_env(tmp_path / "nope.env", {}) == {}


def test_main_refuses_a_bad_payload_before_touching_aws(monkeypatch):
    pytest.importorskip("bedrock_agentcore")
    import asyncio

    monkeypatch.setenv("GRANTHOUND_TABLE", "t")
    monkeypatch.setenv("GRANTHOUND_BUCKET", "b")
    import main  # agent/main.py is on pythonpath via pytest.ini

    result = asyncio.run(main.invoke({}, None))
    assert result["accepted"] is False and "program_ids" in result["error"]


def test_a_failed_cycle_still_releases_the_async_task(monkeypatch):
    """Setup failing must not strand the runtime in HealthyBusy.

    The caller already holds an "accepted" reply, so if run_chunks dies before
    the finally, nothing ever completes the async task and the runtime reports
    busy for ever while evaluating nothing. LiveStore raising on construction
    stands in for a store or seed-file failure; no AWS is reached either way.
    """
    pytest.importorskip("bedrock_agentcore")
    import asyncio

    monkeypatch.setenv("GRANTHOUND_TABLE", "t")
    monkeypatch.setenv("GRANTHOUND_BUCKET", "b")
    import main

    def refuse_to_build():
        raise RuntimeError("store unavailable")

    completed: list[int] = []
    monkeypatch.setattr(main, "LiveStore", refuse_to_build)
    monkeypatch.setattr(main.app, "complete_async_task", completed.append)

    settings = main.Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b"})
    asyncio.run(main.run_chunks([["p-a"]], settings, 123))

    assert completed == [123]


def test_run_chunks_notifies_after_the_chunks_and_a_notify_failure_does_not_block_completion(monkeypatch):
    pytest.importorskip("bedrock_agentcore")
    import asyncio

    import main
    from granthound.config import Settings

    settings = Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b"})
    completed = []
    monkeypatch.setattr(main.app, "complete_async_task", lambda task_id: completed.append(task_id))
    monkeypatch.setattr(main, "LiveStore", lambda: object())
    monkeypatch.setattr(main, "load_seed_file", lambda path: type("S", (), {"org": None})())

    async def fake_batch(ids, at, **kw):
        from granthound.pipeline.finalize import RunSummary
        return RunSummary(run_id="run-x", status="ok", outcomes=[], run_item={"verdict_counts": {}}, errors=[])
    monkeypatch.setattr(main, "run_batch_async", fake_batch)
    seen = []
    def boom(summaries, **kw):
        seen.append(len(summaries))
        raise RuntimeError("telegram exploded")
    monkeypatch.setattr(main, "notify_cycle", boom)

    asyncio.run(main.run_chunks([["p-a"], ["p-b"]], settings, 7))
    assert seen == [2] and completed == [7]


def test_run_chunks_notifies_even_when_every_chunk_fails(monkeypatch):
    """An all-failed cycle must still say so; it must not go silent."""
    pytest.importorskip("bedrock_agentcore")
    import asyncio

    import main
    from granthound.config import Settings

    settings = Settings.from_env({"GRANTHOUND_TABLE": "t", "GRANTHOUND_BUCKET": "b"})
    completed = []
    monkeypatch.setattr(main.app, "complete_async_task", lambda task_id: completed.append(task_id))
    monkeypatch.setattr(main, "LiveStore", lambda: object())
    monkeypatch.setattr(main, "load_seed_file", lambda path: type("S", (), {"org": None})())

    async def always_fails(ids, at, **kw):
        raise RuntimeError("chunk exploded")
    monkeypatch.setattr(main, "run_batch_async", always_fails)

    calls = []
    def spy(summaries, **kw):
        calls.append((summaries, kw.get("chunks_attempted")))
        return "skipped: no GRANTHOUND_TELEGRAM_PARAM"
    monkeypatch.setattr(main, "notify_cycle", spy)

    asyncio.run(main.run_chunks([["p-a"], ["p-b"]], settings, 9))
    assert calls == [([], 2)] and completed == [9]
