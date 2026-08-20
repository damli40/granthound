"""Smoke-test both models via their global inference profiles.

Usage: python scripts/bedrock_smoke.py <haiku_profile_id> <sonnet_profile_id>
"""
import sys

import boto3
from botocore.config import Config

CONFIG = Config(retries={"mode": "adaptive", "total_max_attempts": 5})


def smoke(client, model_id: str) -> str:
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": "Reply with the single word OK."}]}],
        inferenceConfig={"maxTokens": 16},
    )
    return resp["output"]["message"]["content"][0]["text"]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: bedrock_smoke.py <haiku_id> <sonnet_id>", file=sys.stderr)
        return 2
    client = boto3.client("bedrock-runtime", region_name="us-east-1", config=CONFIG)
    for model_id in sys.argv[1:3]:
        text = smoke(client, model_id)
        print(f"{model_id}: {text.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
