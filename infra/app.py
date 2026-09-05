#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stack import GranthoundScheduleStack, GranthoundStoreStack

app = cdk.App()
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

GranthoundStoreStack(app, "GranthoundStore", env=env)

runtime_arn = app.node.try_get_context("runtimeArn")
if runtime_arn:
    GranthoundScheduleStack(app, "GranthoundSchedule", runtime_arn=runtime_arn, env=env)

app.synth()
