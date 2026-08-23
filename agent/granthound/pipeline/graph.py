"""The Strands Graph: scout -> verifier -> (only if something is live) analyst -> clerk.

There is deliberately NO verifier -> clerk edge (design decision D1): when
nothing is live the graph simply ends after the verifier and finalization
(plain code, outside the graph) writes every row. That removes the fan-in
OR-semantics trap the spec warned about. The condition reads the
RunContext through invocation_state (context-aware edge condition), never
a module global.
"""

import json

from strands.agent.base import AgentBase
from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph, GraphState

from granthound.pipeline import stages
from granthound.pipeline.context import RunContext

NODE_IDS = ("scout", "verifier", "analyst", "clerk")
EXECUTION_TIMEOUT_S = 900
# The only bound on a node that keeps calling a tool that keeps rejecting
# it: five of the stage rejection paths are not counted by the per-stage
# rejection counter, so nothing else stops that loop.
NODE_TIMEOUT_S = 300


def needs_analysis_condition(state: GraphState, *, invocation_state: dict, **kwargs) -> bool:
    return bool(stages.needs_analysis(invocation_state["ctx"]))


def build_graph(executors: dict[str, AgentBase]) -> Graph:
    missing = [node_id for node_id in NODE_IDS if node_id not in executors]
    if missing:
        raise ValueError(f"missing executors for node(s): {', '.join(missing)}")
    builder = GraphBuilder()
    for node_id in NODE_IDS:
        builder.add_node(executors[node_id], node_id)
    builder.add_edge("scout", "verifier")
    builder.add_edge("verifier", "analyst", condition=needs_analysis_condition)
    builder.add_edge("analyst", "clerk")
    builder.set_entry_point("scout")
    builder.set_max_node_executions(len(NODE_IDS))
    builder.set_execution_timeout(EXECUTION_TIMEOUT_S)
    builder.set_node_timeout(NODE_TIMEOUT_S)
    return builder.build()


def task_text(ctx: RunContext) -> str:
    return json.dumps({"run_id": ctx.run_id, "program_ids": ctx.program_ids})
