"""Fire one GrantHound cycle on the AgentCore runtime.

The runtime acknowledges in under a second and does the work in an async
task, so this function only needs to survive the ack. A 33+ character
session id is required by InvokeAgentRuntime; a fresh one per fire keeps
cycles from sharing a runtime session.
"""

import json
import os
import uuid

import boto3

RUNTIME_ARN = os.environ["GRANTHOUND_RUNTIME_ARN"]
_client = boto3.client("bedrock-agentcore")


def handler(event, context):
    payload = (event or {}).get("payload") or {"mode": "cycle"}
    session_id = f"schedule-{uuid.uuid4()}-{uuid.uuid4()}"
    response = _client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode("utf-8"),
    )
    body = response.get("response")
    ack = body.read().decode("utf-8", "replace") if hasattr(body, "read") else str(body)
    result = {"session": session_id, "payload": payload, "ack": ack[:2000]}
    print(json.dumps(result))
    return result
