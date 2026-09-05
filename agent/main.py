"""AgentCore Runtime entrypoint for GrantHound.

One POST runs one cycle. The handler validates the payload, reads the
clock once per chunk, and returns an acknowledgement at once while the
chunks run inside an AgentCore async task, so the runtime reports
HealthyBusy (and is not reaped) until the last chunk has finalized.
Configuration comes from runtime.env beside this file (resource names,
no secrets); a real environment variable, if the platform sets one, wins.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from granthound.entrypoint import PayloadError, chunk, load_runtime_env, parse_payload

HERE = Path(__file__).resolve().parent
load_runtime_env(HERE / "runtime.env")

# Store modules read AWS_REGION at import time, so they import after the env file.
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402
from granthound.config import Settings  # noqa: E402
from granthound.pipeline.deterministic import run_id_for  # noqa: E402
from granthound.pipeline.run import run_batch_async  # noqa: E402
from granthound.seeds.profile import DEFAULT_SEED_PATH, load_seed_file  # noqa: E402
from granthound.store.protocol import LiveStore  # noqa: E402
from granthound.tools.fetch import fetch_page  # noqa: E402

app = BedrockAgentCoreApp()
log = app.logger if hasattr(app, "logger") else logging.getLogger("granthound")

# Fire-and-forget tasks must be referenced or the event loop may drop them.
_TASKS: set[asyncio.Task] = set()


async def run_chunks(chunks: list[list[str]], settings: Settings, task_id: int) -> None:
    store = LiveStore()
    org = load_seed_file(DEFAULT_SEED_PATH).org
    last_run_id = None
    try:
        for ids in chunks:
            at = datetime.now(timezone.utc)
            if run_id_for(at) == last_run_id:
                # Run ids have second resolution; two chunks in one second would share a RUN row.
                await asyncio.sleep(1)
                at = datetime.now(timezone.utc)
            last_run_id = run_id_for(at)
            try:
                summary = await run_batch_async(
                    ids, at, store=store, fetcher=fetch_page, org=org, settings=settings
                )
                log.info(
                    "chunk done run_id=%s status=%s outcomes=%s",
                    summary.run_id, summary.status,
                    [(o.program_id, o.verdict.value, o.disposition.value) for o in summary.outcomes],
                )
            except Exception:  # noqa: BLE001 -- one chunk failing must not stop the cycle
                log.exception("chunk failed ids=%s", ids)
    finally:
        app.complete_async_task(task_id)


@app.entrypoint
async def invoke(payload, context):
    try:
        settings = Settings.from_env()
    except KeyError as exc:
        return {"accepted": False, "error": str(exc)}
    store = LiveStore()
    try:
        ids = parse_payload(payload, lambda: [p["program_id"] for p in store.list_programs()])
    except PayloadError as exc:
        return {"accepted": False, "error": str(exc)}
    chunks = chunk(ids)
    task_id = app.add_async_task("cycle", {"programs": len(ids), "chunks": len(chunks)})
    task = asyncio.create_task(run_chunks(chunks, settings, task_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {
        "accepted": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "programs": ids,
        "chunks": chunks,
        "task_id": task_id,
    }


if __name__ == "__main__":
    app.run()
