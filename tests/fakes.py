"""Test doubles shared by the M2 suite. No AWS, no network, no clock.

MemoryStore mirrors the Store protocol over plain dicts. It copies on the
way in and out so a test cannot mutate stored state by accident and then
read its own mutation back as if the pipeline had written it.
"""

import asyncio
import copy
import json
from collections.abc import Callable
from datetime import datetime, timezone

import requests
from strands.agent.agent_result import AgentResult
from strands.telemetry.metrics import EventLoopMetrics

from granthound.pipeline import stages
from granthound.seeds.profile import CommitmentWindow, OrgProfile


class MemoryStore:
    def __init__(self) -> None:
        self.meta: dict[str, dict] = {}
        self.evals: dict[str, dict[str, dict]] = {}
        self.runs: dict[str, dict] = {}
        self.objects: dict[str, str] = {}

    # --- DynamoDB side -------------------------------------------------
    def get_program(self, program_id: str) -> dict | None:
        item = self.meta.get(program_id)
        return copy.deepcopy(item) if item is not None else None

    def put_program_meta(self, item: dict) -> None:
        self.meta[item["program_id"]] = copy.deepcopy(item)

    def put_evaluation(self, program_id: str, run_id: str, eval_item: dict, *, at: datetime) -> str:
        if at.tzinfo is None:
            raise ValueError("at must be a timezone-aware datetime (tzinfo required)")
        sk = f"EVAL#{at.astimezone(timezone.utc).isoformat()}#{run_id}"
        bucket = self.evals.setdefault(program_id, {})
        if sk not in bucket:
            bucket[sk] = {
                **copy.deepcopy(eval_item),
                "program_id": program_id,
                "run_id": run_id,
                "sk": sk,
            }
        return sk

    def get_last_eval(self, program_id: str, *, with_snapshot: bool = False) -> dict | None:
        for sk in sorted(self.evals.get(program_id, {}), reverse=True):
            item = self.evals[program_id][sk]
            if not with_snapshot or item.get("snapshot_receipt") is not None:
                return copy.deepcopy(item)
        return None

    def update_meta_pointers(
        self,
        program_id: str,
        *,
        verdict: str,
        fit_score: float | None,
        latest_eval_sk: str,
        latest_snapshot_sha: str,
    ) -> bool:
        if program_id not in self.meta:
            return False
        self.meta[program_id].update(
            verdict=verdict,
            fit_score=fit_score,
            latest_eval_sk=latest_eval_sk,
            latest_snapshot_sha=latest_snapshot_sha,
        )
        return True

    def list_programs(self) -> list[dict]:
        return [copy.deepcopy(item) for item in self.meta.values()]

    def put_run(self, item: dict) -> None:
        # Runs live in their own dict, never in self.meta -- mirrors the
        # real table, where a run is its own pk partition and must never
        # surface from list_programs().
        self.runs[item["run_id"]] = copy.deepcopy(item)

    # --- S3 side ---------------------------------------------------------
    def put_snapshot(
        self, program_id: str, fetched_at: str, sha256: str, raw_html: str, norm_md: str
    ) -> tuple[str, str]:
        prefix = f"snapshots/{program_id}/{fetched_at}_{sha256[:8]}"
        raw_key, norm_key = f"{prefix}.raw.html", f"{prefix}.norm.md"
        self.objects[raw_key] = raw_html
        self.objects[norm_key] = norm_md
        return raw_key, norm_key

    def put_diff(self, program_id: str, ts: str, old_sha: str, new_sha: str, diff_text: str) -> str:
        key = f"diffs/{program_id}/{ts}_{old_sha[:8]}_{new_sha[:8]}.diff"
        self.objects[key] = diff_text
        return key

    def get_norm_snapshot(self, key: str) -> str:
        return self.objects[key]

    def get_text(self, key: str) -> str:
        return self.objects[key]

    def list_runs(self) -> list[dict]:
        return [copy.deepcopy(item) for item in self.runs.values()]

    def list_evals(self, program_id: str) -> list[dict]:
        return [copy.deepcopy(self.evals[program_id][sk]) for sk in sorted(self.evals.get(program_id, {}))]


def make_fetcher(pages: dict[str, "tuple[int, str] | Exception"]):
    """Build a Fetcher from a url -> (status, body) | exception map.

    An Exception value is raised when that url is fetched, which is how a
    test simulates a transport failure (use requests.ConnectionError).
    """

    def fetcher(url: str) -> tuple[int, str]:
        entry = pages[url]
        if isinstance(entry, Exception):
            raise entry
        return entry

    return fetcher


def html_page(body_text: str) -> str:
    return f"<html><head><title>Fund</title></head><body><main><p>{body_text}</p></main></body></html>"


UNREACHABLE = requests.ConnectionError("connection refused")


# --- M2 graph doubles ------------------------------------------------------

LIVE_URL, DEAD_URL, DOWN_URL = "https://x.org/live", "https://x.org/dead", "https://x.org/down"
# The two deadlines sit 25 days apart on purpose. More than 30 days apart and
# the date scanner calls them contradictory (dates_contradict), the page is
# suggested DATE_CONTRADICTION, and no refinement of that reaches a live
# disposition -- so a fixture with a wider gap can never be scored and every
# happy-path assertion below would fail for a reason that has nothing to do
# with the graph. tests/test_stages.py uses the same dates.
LIVE_PAGE = html_page(
    "Riverbend Community Grants. Applications are due October 5, 2026. "
    "Letters of intent are due September 10, 2026. Eligible applicants are 501(c)(3) "
    "organizations serving Franklin County youth. Awards range from $5,000 to $25,000 per organization."
)
DEAD_PAGE = html_page("2025 Grant Cycle. Applications were due March 1, 2025. Thank you to all applicants.")
ORG = OrgProfile(
    name="Riverbend Youth Collective",
    profile="501(c)(3) youth org, Columbus OH, budget ~$185K.",
    commitment_windows=[CommitmentWindow(label="fall program launch", start="2026-09-01", end="2026-09-20")],
)
PAGES = {LIVE_URL: (200, LIVE_PAGE), DEAD_URL: (200, DEAD_PAGE), DOWN_URL: UNREACHABLE}


def seeded_store() -> MemoryStore:
    store = MemoryStore()
    for pid, url in (("p-live", LIVE_URL), ("p-dead", DEAD_URL), ("p-down", DOWN_URL)):
        store.put_program_meta(
            {"program_id": pid, "url": url, "funder": pid, "source_type": "test", "is_fixture": False}
        )
    return store


def _program_ids_from(prompt) -> list[str]:
    if isinstance(prompt, str):
        text = prompt
    else:
        text = " ".join(block.get("text", "") for block in prompt if isinstance(block, dict))
    start = text.find("{")
    end = text.find("}", start)
    return json.loads(text[start : end + 1])["program_ids"] if start >= 0 else []


Script = Callable[[object, list[str]], None]


class FakeAgent:
    """Scripted stand-in for a Strands Agent node.

    Satisfies the AgentBase protocol (invoke_async, __call__, stream_async),
    runs `script(ctx, program_ids)` against the RunContext the graph passes
    in invocation_state, and yields a real AgentResult so the Graph's
    result/metrics plumbing is exercised unchanged.
    """

    def __init__(self, name: str, script: Script, *, model_id: str = "fake-model") -> None:
        self.name = name
        self.script = script
        self.model_id = model_id
        self.calls = 0

    async def invoke_async(self, prompt=None, **kwargs):
        result = None
        async for event in self.stream_async(prompt, **kwargs):
            if "result" in event:
                result = event["result"]
        return result

    def __call__(self, prompt=None, **kwargs):
        return asyncio.run(self.invoke_async(prompt, **kwargs))

    async def stream_async(self, prompt=None, *, invocation_state=None, **kwargs):
        self.calls += 1
        self.script(invocation_state["ctx"], _program_ids_from(prompt))
        yield {
            "result": AgentResult(
                stop_reason="end_turn",
                message={"role": "assistant", "content": [{"text": f"{self.name} DONE"}]},
                metrics=EventLoopMetrics(),
                state={},
            )
        }


def _noop(ctx, ids) -> None:
    return None


def scripted_executors(scout=None, verifier=None, analyst=None, clerk=None) -> dict[str, FakeAgent]:
    return {
        "scout": FakeAgent("scout", scout or _noop, model_id="fake-haiku"),
        "verifier": FakeAgent("verifier", verifier or _noop, model_id="fake-haiku"),
        "analyst": FakeAgent("analyst", analyst or _noop, model_id="fake-sonnet"),
        "clerk": FakeAgent("clerk", clerk or _noop, model_id="fake-haiku"),
    }


# "Good model" scripts: what a cooperative LLM would do through the tools.
def good_scout(ctx, ids) -> None:
    for pid in ids:
        stages.scout_fetch(ctx, pid)


def good_verifier(ctx, ids) -> None:
    for pid in ids:
        brief = stages.verifier_brief(ctx, pid)
        if brief.startswith("UNREACHABLE"):
            continue
        if "suggested disposition: stale_date_suspect" in brief:
            stages.verifier_record(
                ctx, pid, "verified_dead_prior_year", "prior_cycle_only", ["Applications were due March 1, 2025."]
            )
        else:
            stages.verifier_record(
                ctx, pid, "verified_live", "deadline_in_future", ["Applications are due October 5, 2026."]
            )


def good_analyst(ctx, ids) -> None:
    for pid in stages.needs_analysis(ctx):
        stages.analyst_record(
            ctx, pid,
            5.0, "Eligible applicants are 501(c)(3) organizations serving Franklin County youth.",
            4.0, "Riverbend Community Grants.",
            4.0, "Applications are due October 5, 2026.",
            3.0, "Letters of intent are due September 10, 2026.",
            4.0, "Applications are due October 5, 2026.",
            headline_amount=25000, reachable_amount=25000,
            amount_quote="Awards range from $5,000 to $25,000 per organization.",
        )


def good_clerk(ctx, ids) -> None:
    for pid in stages.needs_package(ctx):
        stages.clerk_record(
            ctx, pid, ["2026-10-05", "2026-09-10"], ["full_application", "loi"],
            ["Awards range from $5,000 to $25,000 per organization."],
            ["Eligible applicants are 501(c)(3) organizations serving Franklin County youth."],
        )
