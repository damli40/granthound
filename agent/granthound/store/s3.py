"""S3 wrapper for the GranthoundStore evidence bucket.

Key scheme:
  snapshots/<program_id>/<fetched_at>_<sha8>.raw.html
  snapshots/<program_id>/<fetched_at>_<sha8>.norm.md
  diffs/<program_id>/<ts>_<old_sha8>_<new_sha8>.diff

Environment contract: GRANTHOUND_BUCKET (bucket name), AWS_REGION
(default us-east-1). Read lazily inside each call so a script can load
`.env` into os.environ before the first store call runs.
"""

import os

import boto3
from botocore.config import Config

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_CONFIG = Config(retries={"mode": "adaptive", "total_max_attempts": 5})

# Module-level shared client.
_s3 = boto3.client("s3", region_name=_REGION, config=_CONFIG)


def _bucket() -> str:
    return os.environ["GRANTHOUND_BUCKET"]


def put_snapshot(
    program_id: str, fetched_at: str, sha256: str, raw_html: str, norm_md: str
) -> tuple[str, str]:
    """Upload the raw and normalized snapshot bodies. Returns (raw_key, norm_key)."""
    sha8 = sha256[:8]
    prefix = f"snapshots/{program_id}/{fetched_at}_{sha8}"
    raw_key = f"{prefix}.raw.html"
    norm_key = f"{prefix}.norm.md"
    bucket = _bucket()

    _s3.put_object(
        Bucket=bucket,
        Key=raw_key,
        Body=raw_html.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    _s3.put_object(
        Bucket=bucket,
        Key=norm_key,
        Body=norm_md.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )
    return raw_key, norm_key


def put_diff(program_id: str, ts: str, old_sha: str, new_sha: str, diff_text: str) -> str:
    """Upload a diff body. Returns the S3 key it was written to."""
    key = f"diffs/{program_id}/{ts}_{old_sha[:8]}_{new_sha[:8]}.diff"
    _s3.put_object(
        Bucket=_bucket(),
        Key=key,
        Body=diff_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    return key


def get_norm_snapshot(key: str) -> str:
    """Fetch and decode a snapshot object's body as text."""
    response = _s3.get_object(Bucket=_bucket(), Key=key)
    body = response["Body"]
    try:
        return body.read().decode("utf-8")
    finally:
        body.close()


def get_text(key: str) -> str:
    """Fetch any text object (snapshot, diff) by key."""
    return get_norm_snapshot(key)
