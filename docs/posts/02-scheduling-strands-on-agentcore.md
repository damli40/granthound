# Agents for Humans: scheduling a Strands graph on AgentCore, the EventBridge to Lambda to InvokeAgentRuntime pattern

GrantHound runs a four-agent Strands graph on Amazon Bedrock AgentCore
Runtime, once every 12 hours, unattended. This post is about the plumbing
between "a schedule fires" and "the graph runs" — not because it's the
interesting part of the product, but because it's the part that silently
breaks a demo if you get it wrong, and nobody writes it up.

## Why the Scheduler needs a Lambda in front of it

EventBridge Scheduler can call a handful of AWS APIs directly as a
target, but `InvokeAgentRuntime` isn't tuned for a fire-and-forget
schedule: the runtime accepts a payload and hands back an acknowledgement,
and the actual cycle — four agents, real page fetches, real model calls —
keeps running after that ack, inside the runtime's own async task
machinery. A raw EventBridge target has no way to read that ack and decide
whether the cycle actually started. So a small Lambda sits in between: it
calls `InvokeAgentRuntime`, reads the response body, and treats anything
that isn't an explicit `{"accepted": true}` as a failure — including a
`200 OK` with an `"accepted": false` inside it, the runtime's quiet way of
declining a cycle (bad payload, missing config). If the Lambda didn't read
the body, that failure would never show up anywhere: no CloudWatch alarm,
just a schedule that "ran" on every tick and quietly did nothing.

```python
def handler(event, context):
    payload = (event or {}).get("payload") or {"mode": "cycle"}
    session_id = f"schedule-{uuid.uuid4()}-{uuid.uuid4()}"
    response = _client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode("utf-8"),
    )
    body = response.get("response")
    raw = body.read().decode("utf-8", "replace") if hasattr(body, "read") else str(body)
    try:
        ack = json.loads(raw)
    except ValueError:
        ack = raw[:2000]
    result = {"session": session_id, "payload": payload, "ack": ack}
    print(json.dumps(result, default=str))
    if not (isinstance(ack, dict) and ack.get("accepted") is True):
        raise RuntimeError(f"runtime refused the cycle: {ack}")
    return result
```

The other thing this Lambda has to not do is retry into a second paid
cycle. `InvokeAgentRuntime` can be slow to ack under load, and boto3's
default retry behavior would happily fire a second identical request on a
timeout — except the first request may have already started the cycle, so
a "helpful" retry means two runs, two sets of model calls, double the
bill, for one scheduled tick. The client is pinned to `total_max_attempts:
1` for exactly this reason.

## The ack-and-async-task shape, on the runtime side

The Lambda's ack has to be real, which means the runtime entrypoint has to
answer fast without waiting for the graph to finish. AgentCore's
`add_async_task` / `complete_async_task` pair is what makes that safe: the
entrypoint calls `add_async_task`, kicks off the actual graph run as a
background `asyncio.Task`, and returns `{"accepted": true, ...}`
immediately. The runtime reports itself as healthy-busy for as long as
that task is open, so it isn't reaped mid-cycle. The matching
`complete_async_task` call lives in a `finally` block around the whole
background coroutine — not after the happy path, in a `finally` — because
if a store write or a seed-file read throws before the graph even starts,
the task still has to close. Skip that and the caller keeps the accepted
reply it already sent, the async task never releases, and the runtime
looks "busy" forever while zero programs get evaluated. That's a failure
mode with no error message anywhere, which is worse than a crash.

## Chunking, and one clock read per chunk

The graph doesn't run all of it in one pass — 20 programs watched as of
run `run-20260906T083424Z` (`docs/measured.md`). Programs are
split into chunks of five (`CHUNK_SIZE = 5`), and each chunk gets its own
run through the graph, with its own timestamp read fresh at the top of the
loop. That timestamp is what generates the run id, so two chunks that land
in the same second would collide on one RUN row — the code checks for
that and sleeps a second rather than let it happen silently. One chunk
failing is logged and skipped, not fatal to the rest of the cycle.

## What the RUN row records

Every run through the graph writes one `RUN#<run_id>/META` item, whether
or not everything in it succeeded: `status`, any `errors`, the exact
`program_ids` in that run, `node_models` (which Bedrock model backed which
node), `node_usage` (token counts per node, per model — the same numbers
`scripts/stats.py` prints as "tokens by node"), `verdict_counts`,
`disposition_counts`, `flag_counts`, and how many verifier calls got
overridden by the deterministic layer. It's written last, deliberately,
and its own write failure is allowed to raise instead of being swallowed —
a run that can't be logged has to fail loudly, because a missing RUN row
reads exactly like "no run happened," and that's not something a
scheduled, unattended system can afford to get wrong quietly.

Repo: https://github.com/damli40/granthound.
