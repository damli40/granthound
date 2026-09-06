"""Fire one GrantHound cycle on the AgentCore runtime.

The runtime acknowledges in under a second and does the work in an async
task, so this function only needs to survive the ack. A 33+ character
session id is required by InvokeAgentRuntime; a fresh one per fire keeps
cycles from sharing a runtime session.

Two things this function must not do quietly. It must not treat a refusal
as success: the runtime answers a rejected payload or a missing config
variable with HTTP 200 and {"accepted": false, ...}, so the ack is read and
a refusal is raised, which is the only way the Lambda Errors metric and the
schedule ever notice that nothing is being evaluated. And it must not let a
slow ack turn into a second paid cycle: botocore is pinned to one attempt
and given a read timeout inside the function timeout, because a retry after
the runtime has already started the cycle would start another one.
"""

import json
import os
import uuid

import boto3
from botocore.config import Config

RUNTIME_ARN = os.environ["GRANTHOUND_RUNTIME_ARN"]
# total_max_attempts=1 means exactly one request, no retry. (botocore's
# "max_attempts" counts retries AFTER the first request, so max_attempts=1
# would still allow two -- and two requests here means two paid cycles.)
_client = boto3.client(
    "bedrock-agentcore",
    config=Config(retries={"total_max_attempts": 1}, read_timeout=45),
)


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
    # Log before raising: a refusal has to be readable in CloudWatch, not just counted.
    print(json.dumps(result, default=str))
    if not (isinstance(ack, dict) and ack.get("accepted") is True):
        raise RuntimeError(f"runtime refused the cycle: {ack}")
    return result
