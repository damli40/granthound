"""The storage seam the pipeline is written against.

Store is a structural Protocol: anything with these methods works. LiveStore
is the production implementation over the boto3 wrappers in ddb.py/s3.py;
tests/fakes.py carries MemoryStore. Keeping the pipeline off the ddb/s3
modules directly is what lets the whole graph run in a unit test with zero
AWS calls and zero mocking libraries.
"""

from datetime import datetime
from typing import Protocol

from granthound.store import ddb, s3


class Store(Protocol):
    def get_program(self, program_id: str) -> dict | None: ...

    def put_program_meta(self, item: dict) -> None: ...

    def put_evaluation(self, program_id: str, run_id: str, eval_item: dict, *, at: datetime) -> str: ...

    def get_last_eval(self, program_id: str, *, with_snapshot: bool = False) -> dict | None: ...

    def update_meta_pointers(
        self,
        program_id: str,
        *,
        verdict: str,
        fit_score: float | None,
        latest_eval_sk: str,
        latest_snapshot_sha: str,
    ) -> bool: ...

    def list_programs(self) -> list[dict]: ...

    def put_run(self, item: dict) -> None: ...

    def put_snapshot(
        self, program_id: str, fetched_at: str, sha256: str, raw_html: str, norm_md: str
    ) -> tuple[str, str]: ...

    def put_diff(self, program_id: str, ts: str, old_sha: str, new_sha: str, diff_text: str) -> str: ...

    def get_norm_snapshot(self, key: str) -> str: ...


class LiveStore:
    """Production Store: thin delegation, no logic of its own."""

    def get_program(self, program_id: str) -> dict | None:
        return ddb.get_program(program_id)

    def put_program_meta(self, item: dict) -> None:
        ddb.put_program_meta(item)

    def put_evaluation(self, program_id: str, run_id: str, eval_item: dict, *, at: datetime) -> str:
        return ddb.put_evaluation(program_id, run_id, eval_item, at=at)

    def get_last_eval(self, program_id: str, *, with_snapshot: bool = False) -> dict | None:
        return ddb.get_last_eval(program_id, with_snapshot=with_snapshot)

    def update_meta_pointers(
        self,
        program_id: str,
        *,
        verdict: str,
        fit_score: float | None,
        latest_eval_sk: str,
        latest_snapshot_sha: str,
    ) -> bool:
        return ddb.update_meta_pointers(
            program_id,
            verdict=verdict,
            fit_score=fit_score,
            latest_eval_sk=latest_eval_sk,
            latest_snapshot_sha=latest_snapshot_sha,
        )

    def list_programs(self) -> list[dict]:
        return ddb.list_programs()

    def put_run(self, item: dict) -> None:
        ddb.put_run(item)

    def put_snapshot(
        self, program_id: str, fetched_at: str, sha256: str, raw_html: str, norm_md: str
    ) -> tuple[str, str]:
        return s3.put_snapshot(program_id, fetched_at, sha256, raw_html, norm_md)

    def put_diff(self, program_id: str, ts: str, old_sha: str, new_sha: str, diff_text: str) -> str:
        return s3.put_diff(program_id, ts, old_sha, new_sha, diff_text)

    def get_norm_snapshot(self, key: str) -> str:
        return s3.get_norm_snapshot(key)
