"""DynamoDB wrapper for the GranthoundStore table.

Single-table layout, one partition per program:
  pk = "PROG#<program_id>"
  sk = "META"                         -- program metadata / pointers
  sk = "EVAL#<utc-iso>#<run_id>"      -- one item per evaluation run

Environment contract: GRANTHOUND_TABLE (table name), AWS_REGION
(default us-east-1). Read lazily inside each call so a script can load
`.env` into os.environ before the first store call runs.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.config import Config

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_CONFIG = Config(retries={"mode": "adaptive", "total_max_attempts": 5})

# Module-level shared resource -- construction is cheap/local, no I/O.
_dynamodb = boto3.resource("dynamodb", region_name=_REGION, config=_CONFIG)


def _table():
    return _dynamodb.Table(os.environ["GRANTHOUND_TABLE"])


def _program_pk(program_id: str) -> str:
    return f"PROG#{program_id}"


def _to_dynamo(value):
    """Recursively convert Python floats to Decimal for a DynamoDB write.

    boto3's resource layer rejects native float outright (TypeError).
    Callers build eval items from pydantic model dumps (FitScore,
    FitAxes, ...) that carry plain floats, so this conversion happens at
    the store boundary rather than leaking a "callers must pass Decimal"
    contract out to every caller.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value):
    """Recursively convert Decimal back to a plain Python number on read.

    Mirror of `_to_dynamo`. An exact-integer Decimal comes back as `int`
    (DynamoDB has no int/float distinction, so this is the only exact
    round-trip available); anything with a fractional part comes back as
    `float`.
    """
    if isinstance(value, Decimal):
        as_int = int(value)
        return as_int if value == as_int else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def put_program_meta(item: dict) -> None:
    """Put/replace the META item for a program.

    `item` must contain a "program_id" key; pk/sk are derived and added.
    """
    program_id = item["program_id"]
    table = _table()
    table.put_item(
        Item=_to_dynamo({**item, "pk": _program_pk(program_id), "sk": "META"})
    )


def get_program(program_id: str) -> dict | None:
    table = _table()
    response = table.get_item(Key={"pk": _program_pk(program_id), "sk": "META"})
    item = response.get("Item")
    return _from_dynamo(item) if item is not None else None


def put_evaluation(program_id: str, run_id: str, eval_item: dict, *, at: datetime) -> str:
    """Put a new EVAL item, conditional on the SK not already existing.

    `at` is the caller-owned run-start timestamp, not a clock read inside
    this function -- a hidden `datetime.now()` here would mint a new
    microsecond (and therefore a new SK) on every application-level
    retry of the same logical run, silently duplicating the EVAL instead
    of no-opping. `at` must be timezone-aware; it is normalized to UTC
    before formatting so the SK's lexicographic order (which
    `get_last_eval`'s ScanIndexForward=False relies on) stays consistent
    regardless of which offset the caller passed.

    Returns the SK it wrote (format `EVAL#<utc-iso>#<run_id>`). On a
    ConditionalCheckFailedException (idempotent replay -- this exact
    pk+sk pair already has an item, i.e. the same run_id retried with
    the same at), returns that same SK rather than raising or
    overwriting the original item.
    """
    if at.tzinfo is None:
        raise ValueError("at must be a timezone-aware datetime (tzinfo required)")

    utc_iso = at.astimezone(timezone.utc).isoformat()
    sk = f"EVAL#{utc_iso}#{run_id}"
    table = _table()
    item = _to_dynamo(
        {
            **eval_item,
            "pk": _program_pk(program_id),
            "sk": sk,
            "program_id": program_id,
            "run_id": run_id,
        }
    )
    try:
        table.put_item(Item=item, ConditionExpression=Attr("sk").not_exists())
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return sk
    return sk


def get_last_eval(program_id: str, *, with_snapshot: bool = False) -> dict | None:
    """Return the most recent EVAL item for a program, or None if none exist.

    With `with_snapshot=False` (default, matches the old behavior): the
    single newest EVAL item regardless of content -- used for run
    bookkeeping (is_first_eval, run counting), where "most recent run of
    any kind" is exactly what's wanted.

    With `with_snapshot=True`: the newest EVAL item whose `snapshot_receipt`
    is non-null, skipping past any newer EVAL items that have none (e.g. a
    PAGE_UNREACHABLE run, which never fetched a page to snapshot). This is
    the correct diff baseline -- diffing against a null snapshot_receipt is
    impossible, so a plain Limit=1 query would silently skip the diff on
    the next successful run instead of comparing against the last real
    snapshot. Paginates a descending Query rather than capping at one page:
    a run of several consecutive outages must not hide a good snapshot
    further back. Each program's EVAL partition is small (one item per
    check run), so full descending pagination is cheap.
    """
    table = _table()
    if not with_snapshot:
        response = table.query(
            KeyConditionExpression=(
                Key("pk").eq(_program_pk(program_id)) & Key("sk").begins_with("EVAL#")
            ),
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return _from_dynamo(items[0]) if items else None

    paginator = table.meta.client.get_paginator("query")
    for page in paginator.paginate(
        TableName=os.environ["GRANTHOUND_TABLE"],
        KeyConditionExpression="pk = :pk AND begins_with(sk, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": _program_pk(program_id),
            ":sk_prefix": "EVAL#",
        },
        ScanIndexForward=False,
    ):
        for item in page.get("Items", []):
            converted = _from_dynamo(item)
            if converted.get("snapshot_receipt") is not None:
                return converted
    return None


def update_meta_pointers(
    program_id: str,
    *,
    verdict: str,
    fit_score: float | None,
    latest_eval_sk: str,
    latest_snapshot_sha: str,
) -> None:
    table = _table()
    table.update_item(
        Key={"pk": _program_pk(program_id), "sk": "META"},
        UpdateExpression=(
            "SET verdict = :verdict, fit_score = :fit_score, "
            "latest_eval_sk = :latest_eval_sk, "
            "latest_snapshot_sha = :latest_snapshot_sha"
        ),
        ExpressionAttributeValues={
            ":verdict": verdict,
            ":fit_score": _to_dynamo(fit_score),
            ":latest_eval_sk": latest_eval_sk,
            ":latest_snapshot_sha": latest_snapshot_sha,
        },
    )


def list_programs() -> list[dict]:
    """Return every program's META item.

    The table only has a pk/sk primary key (no GSI, per the infra spec),
    and each program lives in its own partition (pk="PROG#<id>"), so
    listing across all programs is structurally a Scan, not a Query --
    there is no single partition key that covers every program. Uses the
    scan paginator (never a hand-rolled NextToken loop) filtered to
    sk == "META" so EVAL items are excluded.
    """
    client = _table().meta.client
    paginator = client.get_paginator("scan")
    programs: list[dict] = []
    for page in paginator.paginate(
        TableName=os.environ["GRANTHOUND_TABLE"],
        FilterExpression="sk = :sk",
        ExpressionAttributeValues={":sk": "META"},
    ):
        programs.extend(_from_dynamo(item) for item in page.get("Items", []))
    return programs
