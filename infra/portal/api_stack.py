from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk.aws_apigatewayv2_authorizers import HttpJwtAuthorizer
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration

from .auth_stack import lambda_source
from .config import PortalConfig
from .messaging_stack import email_configuration_set_name

SUMMARY_OBJECTS = "summaries/*"
SUMMARY_PREFIX_PATH = "summaries/"
SESSION_OBJECTS = "verification-sessions/*"
APPROVED_OBJECTS = "approved-summaries/*"
INVITATION_OBJECTS = "invitations/*"
BOUNCE_OBJECTS = "bounces/*"

API_REQUESTS_PER_SECOND = 25
API_BURST = 50

BEDROCK_INFERENCE_PROFILE = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_FOUNDATION_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"


class ApiStack(cdk.Stack):
    def __init__(
        self,
        scope,
        id,
        *,
        config: PortalConfig,
        summaries_bucket: s3.IBucket,
        summaries_key: kms.IKey,
        user_pool: cognito.UserPool,
        user_pool_client_id,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        verification_code = lambda_.Code.from_asset(lambda_source("verification"))

        def verification_function(
            construct_id,
            module,
            timeout: cdk.Duration | None = None,
        ):
            return lambda_.Function(
                self,
                construct_id,
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler=f"{module}.lambda_handler",
                code=verification_code,
                timeout=timeout or cdk.Duration.seconds(10),
                memory_size=256,
                environment={"SUMMARIES_BUCKET": summaries_bucket.bucket_name},
                log_retention=logs.RetentionDays.ONE_MONTH,
            )

        list_interviews = verification_function("ListInterviews", "interviews")
        load_session = verification_function("LoadVerification", "load_session")
        record_verdicts = verification_function("RecordVerdicts", "verdicts")

        prepare_draft = verification_function(
            "PrepareDraft", "drafting", cdk.Duration.seconds(60)
        )
        submit_verification = verification_function("SubmitVerification", "submit")

        for fn in (load_session, record_verdicts, prepare_draft):
            summaries_bucket.grant_read(fn, SUMMARY_OBJECTS)
            summaries_bucket.grant_read_write(fn, SESSION_OBJECTS)
            summaries_key.grant_encrypt_decrypt(fn)

        summaries_bucket.grant_read(list_interviews, SUMMARY_OBJECTS)
        summaries_bucket.grant_read(list_interviews, SESSION_OBJECTS)
        summaries_key.grant_decrypt(list_interviews)

        prepare_draft.add_environment("BEDROCK_MODEL_ID", BEDROCK_INFERENCE_PROFILE)
        prepare_draft.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}:{self.account}:"
                    f"inference-profile/{BEDROCK_INFERENCE_PROFILE}",
                    f"arn:aws:bedrock:*::foundation-model/{BEDROCK_FOUNDATION_MODEL}",
                ],
            )
        )

        summaries_bucket.grant_read_write(submit_verification, SESSION_OBJECTS)
        summaries_bucket.grant_write(submit_verification, APPROVED_OBJECTS)
        summaries_key.grant_encrypt_decrypt(submit_verification)

        submit_verification.add_environment(
            "SES_FROM_ADDRESS", config.ses_from_address
        )
        submit_verification.add_environment(
            "STUDY_TEAM_ADDRESS", config.study_team_address
        )
        submit_verification.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=[
                    f"arn:aws:ses:{self.region}:{self.account}:"
                    f"identity/{config.ses_from_address}"
                ],
            )
        )

        authorizer = HttpJwtAuthorizer(
            "CognitoJwtAuthorizer",
            user_pool.user_pool_provider_url,
            jwt_audience=[user_pool_client_id],
            identity_source=["$request.header.Authorization"],
        )

        http_api = apigw.HttpApi(
            self,
            "PortalApi",
            api_name=f"{config.stack_prefix}-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=config.allowed_origins,
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST],
                allow_headers=["authorization", "content-type"],
            ),
        )

        default_stage = http_api.default_stage.node.default_child
        default_stage.default_route_settings = apigw.CfnStage.RouteSettingsProperty(
            throttling_rate_limit=API_REQUESTS_PER_SECOND,
            throttling_burst_limit=API_BURST,
        )

        http_api.add_routes(
            path="/verification/interviews",
            methods=[apigw.HttpMethod.GET],
            integration=HttpLambdaIntegration(
                "ListInterviewsIntegration", list_interviews
            ),
            authorizer=authorizer,
        )

        http_api.add_routes(
            path="/verification",
            methods=[apigw.HttpMethod.GET],
            integration=HttpLambdaIntegration(
                "LoadVerificationIntegration", load_session
            ),
            authorizer=authorizer,
        )

        http_api.add_routes(
            path="/verification/verdicts",
            methods=[apigw.HttpMethod.POST],
            integration=HttpLambdaIntegration(
                "RecordVerdictsIntegration", record_verdicts
            ),
            authorizer=authorizer,
        )

        http_api.add_routes(
            path="/verification/draft",
            methods=[apigw.HttpMethod.POST],
            integration=HttpLambdaIntegration("PrepareDraftIntegration", prepare_draft),
            authorizer=authorizer,
        )

        http_api.add_routes(
            path="/verification/submit",
            methods=[apigw.HttpMethod.POST],
            integration=HttpLambdaIntegration(
                "SubmitVerificationIntegration", submit_verification
            ),
            authorizer=authorizer,
        )

        send_invitation = verification_function("SendInvitation", "invite")
        send_invitation.add_environment("USER_POOL_ID", user_pool.user_pool_id)
        send_invitation.add_environment("SES_FROM_ADDRESS", config.ses_from_address)
        send_invitation.add_environment(
            "PORTAL_URL",
            config.allowed_origins[0] if config.allowed_origins else "",
        )

        summaries_bucket.grant_read(send_invitation, SUMMARY_OBJECTS)

        summaries_bucket.grant_put(send_invitation, INVITATION_OBJECTS)
        summaries_key.grant_encrypt_decrypt(send_invitation)

        reconcile_invitations = verification_function(
            "ReconcileInvitations", "reconcile", cdk.Duration.seconds(60)
        )
        reconcile_invitations.add_environment("USER_POOL_ID", user_pool.user_pool_id)
        reconcile_invitations.add_environment(
            "SES_FROM_ADDRESS", config.ses_from_address
        )
        reconcile_invitations.add_environment(
            "PORTAL_URL",
            config.allowed_origins[0] if config.allowed_origins else "",
        )

        summaries_bucket.grant_read(reconcile_invitations, SUMMARY_OBJECTS)

        summaries_bucket.grant_read_write(reconcile_invitations, INVITATION_OBJECTS)
        summaries_bucket.grant_delete(reconcile_invitations, INVITATION_OBJECTS)
        summaries_key.grant_encrypt_decrypt(reconcile_invitations)

        configuration_set = email_configuration_set_name(config)

        for fn in (send_invitation, reconcile_invitations):
            fn.add_environment("EMAIL_CONFIGURATION_SET", configuration_set)
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["cognito-idp:ListUsers"],
                    resources=[user_pool.user_pool_arn],
                )
            )
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["ses:SendEmail", "ses:SendRawEmail"],
                    resources=[
                        self.format_arn(
                            service="ses",
                            resource="identity",
                            resource_name=config.ses_from_address,
                        ),
                        self.format_arn(
                            service="ses",
                            resource="configuration-set",
                            resource_name=configuration_set,
                        ),
                    ],
                )
            )

        events.Rule(
            self,
            "ReconcileInvitationsSchedule",
            description=(
                "Hourly sweep for summaries that never produced an invitation."
            ),
            schedule=events.Schedule.rate(cdk.Duration.hours(1)),
            targets=[targets.LambdaFunction(reconcile_invitations)],
        )

        events.Rule(
            self,
            "SummaryArrived",
            description=(
                "A new interview summary landed; invite the participant to check it."
            ),
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [summaries_bucket.bucket_name]},
                    "object": {"key": [{"prefix": SUMMARY_PREFIX_PATH}]},
                },
            ),
            targets=[targets.LambdaFunction(send_invitation)],
        )

        record_bounces = verification_function("RecordBounces", "bounces")
        record_bounces.add_environment("USER_POOL_ID", user_pool.user_pool_id)
        summaries_bucket.grant_put(record_bounces, BOUNCE_OBJECTS)
        summaries_key.grant_encrypt_decrypt(record_bounces)
        record_bounces.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:ListUsers"],
                resources=[user_pool.user_pool_arn],
            )
        )

        events.Rule(
            self,
            "InvitationBounced",
            description=(
                "An invitation bounced; record it so the status report shows the "
                "address is wrong."
            ),
            event_pattern=events.EventPattern(
                source=["aws.ses"],
                detail_type=["Email Bounced"],
                detail={"mail": {"tags": {"ses:configuration-set": [configuration_set]}}},
            ),
            targets=[targets.LambdaFunction(record_bounces)],
        )

        self.api_url = http_api.api_endpoint

        cdk.CfnOutput(
            self,
            "ApiUrl",
            value=http_api.api_endpoint,
            description=(
                "Base URL of the patient API (GET /verification, "
                "POST /verification/verdicts, /draft, /submit)"
            ),
        )
