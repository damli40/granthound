"""Agent factories: one Agent per node, each with its own model instance and
exactly the tools its stage needs. callback_handler=None keeps the SDK's
console printer out of scheduled runs; trace_attributes label the node in
AgentCore Observability."""

from strands import Agent

from granthound.agents import prompts, tools
from granthound.agents.models import analyst_model, haiku
from granthound.config import Settings


def _agent(name: str, model, system_prompt: str, node_tools: list) -> Agent:
    return Agent(
        name=name,
        model=model,
        system_prompt=system_prompt,
        tools=node_tools,
        callback_handler=None,
        trace_attributes={"granthound.node": name},
    )


def make_scout(model) -> Agent:
    return _agent("scout", model, prompts.SCOUT, [tools.fetch_and_snapshot])


def make_verifier(model) -> Agent:
    return _agent("verifier", model, prompts.VERIFIER, [tools.get_verification_brief, tools.record_verification])


def make_analyst(model) -> Agent:
    return _agent("analyst", model, prompts.ANALYST, [tools.get_analysis_brief, tools.record_fit])


def make_clerk(model) -> Agent:
    return _agent("clerk", model, prompts.CLERK, [tools.get_decision_brief, tools.record_decision_package])


def default_executors(settings: Settings) -> dict[str, Agent]:
    return {
        "scout": make_scout(haiku(settings)),
        "verifier": make_verifier(haiku(settings)),
        "analyst": make_analyst(analyst_model(settings)),
        "clerk": make_clerk(haiku(settings)),
    }
