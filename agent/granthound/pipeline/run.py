"""Run one batch of programs through the graph and finalize, whatever happens.

A node exception propagates out of Graph.invoke_async (verified on
strands-agents 1.52.0), so the graph call sits in try/except and
finalization sits in finally. The status starts at "partial" and is only
promoted to "ok" when the graph reports COMPLETED, so a run cut short by
something no `except Exception` can catch (a cancellation, a
KeyboardInterrupt) still writes rows labelled partial rather than rows
that claim a full pass happened.
"""

import asyncio
from datetime import datetime

from strands.agent.base import AgentBase
from strands.multiagent.base import Status

from granthound.agents.factories import default_executors
from granthound.agents.models import model_id_of
from granthound.config import Settings
from granthound.pipeline.context import RunContext
from granthound.pipeline.deterministic import Fetcher
from granthound.pipeline.finalize import RunSummary, finalize_run
from granthound.pipeline.graph import NODE_IDS, build_graph, task_text
from granthound.seeds.profile import OrgProfile
from granthound.store.models import NodeUsage
from granthound.store.protocol import Store


def resolve_targets(
    program_ids: list[str], store: Store, *, url_overrides: dict[str, str] | None = None
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    missing: list[str] = []
    for pid in sorted(set(program_ids)):
        url = (url_overrides or {}).get(pid)
        if url is None:
            url = (store.get_program(pid) or {}).get("url")
        if not url:
            missing.append(pid)
            continue
        targets.append((pid, url))
    if missing:
        raise ValueError(
            f"no stored url for program(s): {', '.join(missing)}; run scripts/seed_load.py first or pass --url"
        )
    return targets


def usage_from_results(results: dict, node_models: dict[str, str]) -> dict[str, NodeUsage]:
    usage: dict[str, NodeUsage] = {}
    for node_id, node_result in results.items():
        counts = node_result.accumulated_usage or {}
        usage[node_id] = NodeUsage(
            model_id=node_models.get(node_id),
            input_tokens=int(counts.get("inputTokens", 0)),
            output_tokens=int(counts.get("outputTokens", 0)),
            total_tokens=int(counts.get("totalTokens", 0)),
            execution_ms=int(node_result.execution_time or 0),
        )
    return usage


async def run_batch_async(
    program_ids: list[str],
    at: datetime,
    *,
    store: Store,
    fetcher: Fetcher,
    org: OrgProfile,
    settings: Settings | None = None,
    executors: dict[str, AgentBase] | None = None,
    url_overrides: dict[str, str] | None = None,
) -> RunSummary:
    targets = resolve_targets(program_ids, store, url_overrides=url_overrides)
    ctx = RunContext.create(targets, at, store=store, fetcher=fetcher, org=org)
    if executors is None:
        if settings is None:
            raise ValueError("settings are required to build the default Bedrock executors")
        executors = default_executors(settings)
    graph = build_graph(executors)
    # Only the graph's own nodes: the run item's node_models is a receipt of
    # what this run billed, so an extra executor the graph never ran must not
    # appear in it.
    ctx.node_models = {node_id: model_id_of(executors[node_id]) for node_id in NODE_IDS}

    status, error = "partial", "the graph did not finish"
    try:
        result = await graph.invoke_async(task_text(ctx), invocation_state={"ctx": ctx})
    except Exception as exc:  # noqa: BLE001 -- the graph failing is a recorded outcome, not a crash
        status, error = "partial", f"{type(exc).__name__}: {exc}"
    else:
        if result.status is Status.COMPLETED:
            status, error = "ok", None
        else:
            status, error = "partial", f"graph status {result.status.value}"
    finally:
        # graph.state.results is the very dict a GraphResult carries, and it
        # holds every node that finished before a failure -- so one read
        # covers the completed, the failed and the cancelled path alike.
        summary = finalize_run(
            ctx,
            node_usage=usage_from_results(graph.state.results, ctx.node_models),
            pipeline_status=status,
            error=error,
        )
    return summary


def run_batch(
    program_ids: list[str],
    at: datetime,
    *,
    store: Store,
    fetcher: Fetcher,
    org: OrgProfile,
    settings: Settings | None = None,
    executors: dict[str, AgentBase] | None = None,
    url_overrides: dict[str, str] | None = None,
) -> RunSummary:
    return asyncio.run(
        run_batch_async(
            program_ids, at, store=store, fetcher=fetcher, org=org,
            settings=settings, executors=executors, url_overrides=url_overrides,
        )
    )
