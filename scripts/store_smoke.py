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
from datetime import datetime, timedelta, timezone
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
SEQ_PROGRAM_ID = "smoke-test-seq"


def cleanup(
    table,
    bucket_name: str,
    s3_client,
    eval_sk: str | None,
    s3_keys: list[str],
    extra_eval_sks: list[str] | None = None,
) -> None:
    table.delete_item(Key={"pk": f"PROG#{PROGRAM_ID}", "sk": "META"})
    if eval_sk is not None:
        table.delete_item(Key={"pk": f"PROG#{PROGRAM_ID}", "sk": eval_sk})
    for sk in extra_eval_sks or []:
        table.delete_item(Key={"pk": f"PROG#{SEQ_PROGRAM_ID}", "sk": sk})
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
    sequence_sks: list[str] = []

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

        # put_evaluation: `at` must be a required, caller-owned, tz-aware
        # timestamp -- reject a naive datetime outright.
        try:
            ddb.put_evaluation(PROGRAM_ID, RUN_ID, {}, at=datetime.now())
        except ValueError:
            pass
        else:
            raise AssertionError("put_evaluation accepted a naive (non-tz-aware) 'at'")

        # eval_item carries a nested dict of native floats (as a real
        # FitAxes/FitScore model dump would) to prove the store-boundary
        # Decimal conversion works recursively, not just on top-level
        # scalars.
        at = datetime.now(timezone.utc)
        fit_axes = {
            "eligibility": 4.72,
            "explicit_funding": 3.1,
            "effort_to_award": 5.0,
            "strategic": 2.25,
            "reliability": 0.0,
        }
        eval_sk = ddb.put_evaluation(
            PROGRAM_ID,
            RUN_ID,
            {"disposition": "added", "note": "smoke test evaluation", "fit_axes": fit_axes},
            at=at,
        )
        assert eval_sk == f"EVAL#{at.isoformat()}#{RUN_ID}"

        last_eval = ddb.get_last_eval(PROGRAM_ID)
        assert last_eval is not None, "get_last_eval returned None"
        assert last_eval["sk"] == eval_sk
        assert last_eval["disposition"] == "added"

        # Float round-trip through the write/read Decimal boundary:
        # fractional values come back as float; the exact-integer value
        # (5.0) is allowed to come back as int (DynamoDB has no
        # int/float distinction) but must still be numerically 5 and
        # never a raw Decimal leaking out of the wrapper.
        got_axes = last_eval["fit_axes"]
        for key, expected in fit_axes.items():
            assert got_axes[key] == expected, f"fit_axes[{key}] did not round-trip"
            assert not hasattr(got_axes[key], "as_tuple"), (
                f"fit_axes[{key}] leaked a Decimal instead of int/float"
            )
        assert isinstance(got_axes["eligibility"], float)

        # Idempotent replay: the SAME (run_id, at) must land on the SAME
        # SK and no-op rather than overwrite -- this is the whole point
        # of making `at` caller-owned instead of a hidden clock read.
        # A different eval_item payload on the replay call proves the
        # original item's data survives untouched.
        replay_sk = ddb.put_evaluation(
            PROGRAM_ID,
            RUN_ID,
            {"disposition": "REPLAY-SHOULD-NOT-STICK"},
            at=at,
        )
        assert replay_sk == eval_sk, "replay with the same (run_id, at) minted a new SK"
        replayed = ddb.get_last_eval(PROGRAM_ID)
        assert replayed["disposition"] == "added", (
            "idempotent replay overwrote the original EVAL item"
        )

        # get_last_eval(with_snapshot=True) diff-baseline seam (final
        # review finding 3): a three-eval sequence in its own partition --
        # good (snapshot_receipt set) -> unreachable (None) -> unreachable
        # (None) again -- proves two things at once: (a) the default,
        # with_snapshot=False call is untouched and still returns the
        # newest EVAL regardless of content; (b) with_snapshot=True walks
        # PAST both null-receipt outage evals and returns the oldest item
        # in the sequence, because it is the only one with a receipt --
        # not just the one immediately before the latest.
        seq_base = datetime.now(timezone.utc)
        seq1_at = seq_base
        seq2_at = seq_base + timedelta(seconds=1)
        seq3_at = seq_base + timedelta(seconds=2)

        seq1_sk = ddb.put_evaluation(
            SEQ_PROGRAM_ID,
            "smoke-seq-1",
            {
                "disposition": "added",
                "snapshot_receipt": {
                    "sha256": "seq1sha",
                    "s3_raw": "raw/seq1",
                    "s3_norm": "norm/seq1",
                    "fetched_at": "20260101T000000Z",
                    "http_status": 200,
                },
            },
            at=seq1_at,
        )
        sequence_sks.append(seq1_sk)

        seq2_sk = ddb.put_evaluation(
            SEQ_PROGRAM_ID,
            "smoke-seq-2",
            {"disposition": "page_unreachable", "snapshot_receipt": None},
            at=seq2_at,
        )
        sequence_sks.append(seq2_sk)

        seq3_sk = ddb.put_evaluation(
            SEQ_PROGRAM_ID,
            "smoke-seq-3",
            {"disposition": "page_unreachable", "snapshot_receipt": None},
            at=seq3_at,
        )
        sequence_sks.append(seq3_sk)

        seq_latest = ddb.get_last_eval(SEQ_PROGRAM_ID)
        assert seq_latest is not None
        assert seq_latest["sk"] == seq3_sk, (
            "get_last_eval() without with_snapshot must still return the newest EVAL "
            "regardless of snapshot_receipt"
        )

        seq_diff_baseline = ddb.get_last_eval(SEQ_PROGRAM_ID, with_snapshot=True)
        assert seq_diff_baseline is not None, (
            "get_last_eval(with_snapshot=True) found no receipt-bearing EVAL"
        )
        assert seq_diff_baseline["sk"] == seq1_sk, (
            "get_last_eval(with_snapshot=True) must skip past the null-receipt "
            "outage evals and return the oldest (first) eval in the sequence, "
            "since it is the only one with a snapshot_receipt"
        )
        assert seq_diff_baseline["snapshot_receipt"]["sha256"] == "seq1sha"

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
        assert updated["fit_score"] == 2.5
        assert isinstance(updated["fit_score"], float)
        assert updated["latest_eval_sk"] == eval_sk
        assert updated["latest_snapshot_sha"] == "deadbeef"

        # update_meta_pointers with fit_score=None must also round-trip
        # (a materially different DynamoDB code path -- NULL, not Decimal).
        ddb.update_meta_pointers(
            PROGRAM_ID,
            verdict="PASS",
            fit_score=None,
            latest_eval_sk=eval_sk,
            latest_snapshot_sha="deadbeef",
        )
        cleared = ddb.get_program(PROGRAM_ID)
        assert cleared["fit_score"] is None

        # put_snapshot / get_norm_snapshot. Compute both deterministic
        # keys up front and register them for cleanup BEFORE calling
        # put_snapshot -- put_snapshot does two separate S3 puts, so if
        # the raw put succeeds and the norm put fails, the raw object
        # must still be tracked for (best-effort) deletion rather than
        # only being registered after both puts return.
        raw_html = "<html><body>Smoke test raw content</body></html>"
        norm_md = "# Smoke test\n\nNormalized snapshot body."
        sha256 = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
        fetched_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sha8 = sha256[:8]
        raw_key = f"snapshots/{PROGRAM_ID}/{fetched_at}_{sha8}.raw.html"
        norm_key = f"snapshots/{PROGRAM_ID}/{fetched_at}_{sha8}.norm.md"
        s3_keys.extend([raw_key, norm_key])

        got_raw_key, got_norm_key = s3.put_snapshot(
            PROGRAM_ID, fetched_at, sha256, raw_html, norm_md
        )
        assert got_raw_key == raw_key
        assert got_norm_key == norm_key

        round_tripped = s3.get_norm_snapshot(norm_key)
        assert round_tripped == norm_md, "norm snapshot did not round-trip"

        # put_diff -- same up-front-key-registration pattern, for
        # consistency and so a partial failure can't orphan the object.
        old_sha = "a" * 64
        new_sha = "b" * 64
        diff_key = f"diffs/{PROGRAM_ID}/{fetched_at}_{old_sha[:8]}_{new_sha[:8]}.diff"
        s3_keys.append(diff_key)
        got_diff_key = s3.put_diff(
            PROGRAM_ID, fetched_at, old_sha, new_sha, "- old line\n+ new line\n"
        )
        assert got_diff_key == diff_key

    finally:
        cleanup(table, bucket_name, s3_client, eval_sk, s3_keys, extra_eval_sks=sequence_sks)

        # Verify cleanup actually left the table/bucket clean.
        assert ddb.get_program(PROGRAM_ID) is None, "META item survived cleanup"
        if eval_sk is not None:
            leftover = table.get_item(
                Key={"pk": f"PROG#{PROGRAM_ID}", "sk": eval_sk}
            ).get("Item")
            assert leftover is None, "EVAL item survived cleanup"
        for sk in sequence_sks:
            leftover = table.get_item(
                Key={"pk": f"PROG#{SEQ_PROGRAM_ID}", "sk": sk}
            ).get("Item")
            assert leftover is None, f"sequence EVAL item {sk} survived cleanup"


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
