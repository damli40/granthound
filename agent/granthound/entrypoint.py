"""Payload rules for the AgentCore entrypoint. Pure: no AWS, no clock, no I/O
beyond reading runtime.env.

The entrypoint accepts exactly one of two shapes:
  {"program_ids": ["a", "b"]}          run exactly these programs
  {"mode": "cycle", "limit": 5?}       run every program the store knows
"limit" belongs to cycle mode only. Anything else is a PayloadError the
caller turns into an error reply, never a run -- an unrecognised key
included, because a typo has to fail loudly rather than quietly change what
runs: {"mode": "cycle", "limt": 3} would otherwise evaluate the entire
catalogue and report success, and {"program_ids": [...], "limit": 2} would
drop the limit without saying so.

Chunks are five programs wide (M2 -> M3 contract): one clock read per chunk
keeps every program in it judged against the same day, and five is what
keeps the Scout under its node timeout.
"""

import os
from collections.abc import Callable, MutableMapping
from pathlib import Path

CHUNK_SIZE = 5
MODES = ("cycle",)


class PayloadError(ValueError):
    """The payload is not one of the accepted shapes."""


def load_runtime_env(path: Path, environ: MutableMapping[str, str] | None = None) -> dict[str, str]:
    """Apply KEY=VALUE lines from `path` to `environ` without overriding.

    A variable the platform already set wins over the file; the file only
    fills gaps. Returns the variables it supplied. A missing file supplies
    nothing (local runs carry their own .env).
    """
    env = os.environ if environ is None else environ
    applied: dict[str, str] = {}
    if not path.exists():
        return applied
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in env:
            env[key] = value
            applied[key] = value
    return applied


def parse_payload(payload, known_ids: Callable[[], list[str]]) -> list[str]:
    """Return the sorted program ids a payload asks for, or raise PayloadError.

    `known_ids` is called only in cycle mode, so a bad payload never costs a
    store read.
    """
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a JSON object")
    unknown = set(payload) - {"program_ids", "mode", "limit"}
    if unknown:
        raise PayloadError(f'unknown payload key(s): {", ".join(sorted(unknown))}')
    has_ids = "program_ids" in payload
    has_mode = "mode" in payload
    if has_ids == has_mode:
        raise PayloadError('payload needs exactly one of "program_ids" or "mode"')
    if has_ids:
        if "limit" in payload:
            raise PayloadError('"limit" only applies to mode')
        ids = payload["program_ids"]
        if not isinstance(ids, list) or not ids or not all(isinstance(pid, str) and pid for pid in ids):
            raise PayloadError('"program_ids" must be a non-empty list of non-empty strings')
        if len(set(ids)) != len(ids):
            raise PayloadError('"program_ids" contains a duplicate')
        return sorted(ids)
    mode = payload["mode"]
    if mode not in MODES:
        raise PayloadError(f'"mode" must be one of {", ".join(MODES)}')
    limit = payload.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise PayloadError('"limit" must be a positive integer')
    ids = sorted(known_ids())
    return ids[:limit] if limit else ids


def chunk(ids: list[str], size: int = CHUNK_SIZE) -> list[list[str]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]
