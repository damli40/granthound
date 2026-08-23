"""Test doubles shared by the M2 suite. No AWS, no network, no clock.

MemoryStore mirrors the Store protocol over plain dicts. It copies on the
way in and out so a test cannot mutate stored state by accident and then
read its own mutation back as if the pipeline had written it.
"""

import copy
from datetime import datetime, timezone

import requests


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
