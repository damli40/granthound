"""Integration smoke test for granthound.store.ddb / granthound.store.s3.

Not mocked -- this hits the real deployed GranthoundStore table + bucket.
Exercises every wrapper function against a throwaway "smoke-test" program,
then deletes what it wrote so the table/bucket stay clean.

Usage: .venv/bin/python scripts/store_smoke.py
Expected: prints OK and exits 0.
"""

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "agent"
sys.path.insert(0, str(AGENT_DIR))


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader -- only sets vars not already in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(REPO_ROOT / ".env")

import boto3  # noqa: E402

from granthound.store import ddb, s3  # noqa: E402

PROGRAM_ID = "smoke-test"
RUN_ID = "smoke-run-1"


def cleanup(table, bucket_name: str, s3_client, eval_sk: str | None, s3_keys: list[str]) -> None:
    table.delete_item(Key={"pk": f"PROG#{PROGRAM_ID}", "sk": "META"})
    if eval_sk is not None:
        table.delete_item(Key={"pk": f"PROG#{PROGRAM_ID}", "sk": eval_sk})
    if s3_keys:
        s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": key} for key in s3_keys]},
        )


def run() -> None:
    region = os.environ.get("AWS_REGION", "us-east-1")
    table = boto3.resource("dynamodb", region_name=region).Table(
        os.environ["GRANTHOUND_TABLE"]
    )
    s3_client = boto3.client("s3", region_name=region)
    bucket_name = os.environ["GRANTHOUND_BUCKET"]

    eval_sk = None
    s3_keys: list[str] = []

    try:
        # put_program_meta / get_program / list_programs
        ddb.put_program_meta(
            {
                "program_id": PROGRAM_ID,
                "funder": "Smoke Test Funder",
                "url": "https://example.org/smoke",
            }
        )
        program = ddb.get_program(PROGRAM_ID)
        assert program is not None, "get_program returned None after put"
        assert program["program_id"] == PROGRAM_ID

        programs = ddb.list_programs()
        assert any(p["program_id"] == PROGRAM_ID for p in programs), (
            "list_programs did not include the smoke-test META item"
        )

        # put_evaluation / get_last_eval
        eval_sk = ddb.put_evaluation(
            PROGRAM_ID,
            RUN_ID,
            {"disposition": "added", "note": "smoke test evaluation"},
        )
        assert eval_sk.startswith("EVAL#") and eval_sk.endswith(RUN_ID)

        last_eval = ddb.get_last_eval(PROGRAM_ID)
        assert last_eval is not None, "get_last_eval returned None"
        assert last_eval["sk"] == eval_sk
        assert last_eval["disposition"] == "added"

        # update_meta_pointers
        ddb.update_meta_pointers(
            PROGRAM_ID,
            verdict="WATCH",
            fit_score=2.5,
            latest_eval_sk=eval_sk,
            latest_snapshot_sha="deadbeef",
        )
        updated = ddb.get_program(PROGRAM_ID)
        assert updated is not None
        assert updated["verdict"] == "WATCH"
        assert float(updated["fit_score"]) == 2.5
        assert updated["latest_eval_sk"] == eval_sk
        assert updated["latest_snapshot_sha"] == "deadbeef"

        # put_snapshot / get_norm_snapshot
        raw_html = "<html><body>Smoke test raw content</body></html>"
        norm_md = "# Smoke test\n\nNormalized snapshot body."
        sha256 = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
        fetched_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        raw_key, norm_key = s3.put_snapshot(
            PROGRAM_ID, fetched_at, sha256, raw_html, norm_md
        )
        s3_keys.extend([raw_key, norm_key])
        assert raw_key == f"snapshots/{PROGRAM_ID}/{fetched_at}_{sha256[:8]}.raw.html"
        assert norm_key == f"snapshots/{PROGRAM_ID}/{fetched_at}_{sha256[:8]}.norm.md"

        round_tripped = s3.get_norm_snapshot(norm_key)
        assert round_tripped == norm_md, "norm snapshot did not round-trip"

        # put_diff
        diff_key = s3.put_diff(
            PROGRAM_ID,
            fetched_at,
            "a" * 64,
            "b" * 64,
            "- old line\n+ new line\n",
        )
        s3_keys.append(diff_key)
        assert diff_key == f"diffs/{PROGRAM_ID}/{fetched_at}_aaaaaaaa_bbbbbbbb.diff"

    finally:
        cleanup(table, bucket_name, s3_client, eval_sk, s3_keys)

        # Verify cleanup actually left the table/bucket clean.
        assert ddb.get_program(PROGRAM_ID) is None, "META item survived cleanup"
        if eval_sk is not None:
            leftover = table.get_item(
                Key={"pk": f"PROG#{PROGRAM_ID}", "sk": eval_sk}
            ).get("Item")
            assert leftover is None, "EVAL item survived cleanup"


def main() -> int:
    try:
        run()
    except Exception as exc:  # noqa: BLE001 -- top-level smoke entrypoint
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
