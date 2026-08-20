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


def put_program_meta(item: dict) -> None:
    """Put/replace the META item for a program.

    `item` must contain a "program_id" key; pk/sk are derived and added.
    """
    program_id = item["program_id"]
    table = _table()
    table.put_item(
        Item={**item, "pk": _program_pk(program_id), "sk": "META"}
    )


def get_program(program_id: str) -> dict | None:
    table = _table()
    response = table.get_item(Key={"pk": _program_pk(program_id), "sk": "META"})
    return response.get("Item")


def put_evaluation(program_id: str, run_id: str, eval_item: dict) -> str:
    """Put a new EVAL item, conditional on the SK not already existing.

    Returns the SK it wrote (format `EVAL#<utc-iso>#<run_id>`). On a
    ConditionalCheckFailedException (idempotent replay -- this exact
    pk+sk pair already has an item), returns that same SK rather than
    raising, since the caller only needs to know which SK the run lives
    at.
    """
    utc_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    sk = f"EVAL#{utc_iso}#{run_id}"
    table = _table()
    item = {
        **eval_item,
        "pk": _program_pk(program_id),
        "sk": sk,
        "program_id": program_id,
        "run_id": run_id,
    }
    try:
        table.put_item(Item=item, ConditionExpression=Attr("sk").not_exists())
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return sk
    return sk


def get_last_eval(program_id: str) -> dict | None:
    table = _table()
    response = table.query(
        KeyConditionExpression=(
            Key("pk").eq(_program_pk(program_id)) & Key("sk").begins_with("EVAL#")
        ),
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None


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
            ":fit_score": Decimal(str(fit_score)) if fit_score is not None else None,
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
        programs.extend(page.get("Items", []))
    return programs
