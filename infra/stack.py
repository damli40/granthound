"""GranthoundStore stack: one DynamoDB table + one S3 evidence bucket.

Hackathon lifecycle: both resources are RemovalPolicy.DESTROY so `cdk destroy`
leaves nothing behind. Nothing else lives in this stack -- Lambdas and the
Scheduler arrive in the M3 plan.
"""

import json
from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_scheduler as scheduler
from constructs import Construct


class GranthoundStoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.Table(
            self,
            "Table",
            partition_key=dynamodb.Attribute(
                name="pk", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sk", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        bucket = s3.Bucket(
            self,
            "EvidenceBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)


INFRA_DIR = Path(__file__).resolve().parent


class GranthoundScheduleStack(Stack):
    """EventBridge Scheduler -> trigger Lambda -> InvokeAgentRuntime, every 12 hours.

    The runtime ARN is a CDK context value (-c runtimeArn=...) read from
    infra/runtime-arn.txt, so this stack can only be synthesized after the
    runtime exists.
    """

    def __init__(self, scope: Construct, construct_id: str, *, runtime_arn: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        if not runtime_arn.startswith("arn:aws:bedrock-agentcore:"):
            raise ValueError(f"runtimeArn context does not look like a runtime ARN: {runtime_arn!r}")

        code_dir = INFRA_DIR / "lambdas" / "trigger"
        build_dir = code_dir / "build"
        asset_dir = build_dir if (build_dir / "handler.py").exists() else code_dir
        trigger = _lambda.Function(
            self,
            "Trigger",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(asset_dir)),
            timeout=Duration.seconds(60),
            environment={"GRANTHOUND_RUNTIME_ARN": runtime_arn},
        )
        trigger.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[runtime_arn, f"{runtime_arn}/*"],
            )
        )

        role = iam.Role(self, "SchedulerRole", assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"))
        trigger.grant_invoke(role)
        scheduler.CfnSchedule(
            self,
            "Every12h",
            schedule_expression="rate(12 hours)",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            target=scheduler.CfnSchedule.TargetProperty(
                arn=trigger.function_arn,
                role_arn=role.role_arn,
                input=json.dumps({"payload": {"mode": "cycle"}}),
                # Scheduler's defaults are 185 attempts over 24 hours. Firing the
                # cycle is not idempotent -- a retry after the runtime already
                # accepted starts a second paid cycle -- so the blast radius is
                # capped at two extra tries inside 15 minutes, which still covers
                # a transient Lambda throttle and stops well short of the next
                # scheduled fire.
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(
                    maximum_retry_attempts=2,
                    maximum_event_age_in_seconds=900,
                ),
            ),
        )
        CfnOutput(self, "TriggerFunctionName", value=trigger.function_name)


WEB_DIR = INFRA_DIR.parent / "web"


class GranthoundWebStack(Stack):
    """The static inbox: private bucket, CloudFront in front, web/ uploaded on deploy.

    Caching is disabled at the edge because the site is a few hundred
    kilobytes and data.json must show the latest export the moment it is
    deployed; a stale receipt page would be worse than a slow one.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        bucket = s3.Bucket(
            self,
            "Site",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            ),
            # A private S3 origin answers a missing/unlisted key with 403, not 404,
            # and a directory-style path like /fixtures/sunset-fund/ (no index.html
            # in the request) is exactly that: no such key. Map both 403 and 404
            # back to the single-page app's index so a fixture folder link (or any
            # deep link) renders the inbox instead of raw S3 AccessDenied XML.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )
        # Two BucketDeployments, not one, because content_type on BucketDeployment
        # applies to the whole deployment, not per file, and deadlines.ics needs
        # text/calendar while everything else keeps its guessed type. The .ics
        # deployment must run with prune=False: a pruning deployment deletes any
        # bucket key its own sources didn't just write, so two pruning
        # deployments into the same bucket would each erase what the other one
        # uploaded (the main deploy would delete deadlines.ics on every deploy,
        # and vice versa for everything else).
        deploy = s3deploy.BucketDeployment(
            self,
            "Deploy",
            sources=[s3deploy.Source.asset(str(WEB_DIR), exclude=["deadlines.ics"])],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )
        deploy_ics = s3deploy.BucketDeployment(
            self,
            "DeployDeadlinesIcs",
            sources=[s3deploy.Source.asset(str(WEB_DIR), exclude=["**", "!deadlines.ics"])],
            destination_bucket=bucket,
            content_type="text/calendar",
            prune=False,
            distribution=distribution,
            distribution_paths=["/deadlines.ics"],
        )
        # CloudFormation has no natural ordering between these two custom
        # resources -- neither references the other's output -- so without an
        # explicit dependency it can run DeployDeadlinesIcs before Deploy, and
        # Deploy (prune=True, and deadlines.ics is outside its own manifest)
        # then deletes the .ics key that DeployDeadlinesIcs just wrote. Forcing
        # DeployDeadlinesIcs to run after Deploy on every deployment is what
        # actually keeps deadlines.ics in the bucket.
        deploy_ics.node.add_dependency(deploy)
        CfnOutput(self, "SiteUrl", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "FixtureUrl", value=f"https://{distribution.distribution_domain_name}/fixtures/sunset-fund/index.html")
