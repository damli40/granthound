"""Runtime settings, validated once at startup, before any model is built.

Every missing variable is named in one error (they are set together and
forgotten together); an empty string counts as missing (a forgotten CDK
context value arrives as "" not as absent). Model ids default to the
global inference profiles recorded in M0 Task 0 and can be overridden per
environment -- the run log records what was actually used.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

HAIKU_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET_MODEL_ID = "global.anthropic.claude-sonnet-5"
DEFAULT_REGION = "us-east-1"

_REQUIRED = ("GRANTHOUND_TABLE", "GRANTHOUND_BUCKET")


@dataclass(frozen=True, kw_only=True)
class Settings:
    table: str
    bucket: str
    region: str
    haiku_model_id: str
    analyst_model_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env

        def read(name: str) -> str:
            return (source.get(name) or "").strip()

        missing = [name for name in _REQUIRED if not read(name)]
        if missing:
            raise KeyError(f"missing required environment variables: {', '.join(missing)}")
        return cls(
            table=read("GRANTHOUND_TABLE"),
            bucket=read("GRANTHOUND_BUCKET"),
            region=read("AWS_REGION") or DEFAULT_REGION,
            haiku_model_id=read("GRANTHOUND_HAIKU_MODEL_ID") or HAIKU_MODEL_ID,
            analyst_model_id=read("GRANTHOUND_ANALYST_MODEL_ID") or SONNET_MODEL_ID,
        )
