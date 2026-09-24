from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs

from .config import PortalConfig


def lambda_source(name):
    return str(Path(__file__).resolve().parent.parent.parent / "lambda" / name)


class AuthStack(cdk.Stack):
    def __init__(self, scope, id, *, config: PortalConfig, **kwargs):
        super().__init__(scope, id, **kwargs)

        is_prod = config.env_name == "prod"
        auth_code = lambda_.Code.from_asset(lambda_source("auth"))

        def trigger(construct_id, module):
            return lambda_.Function(
                self,
                construct_id,
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler=f"{module}.lambda_handler",
                code=auth_code,
                timeout=cdk.Duration.seconds(10),
                memory_size=256,
                log_retention=logs.RetentionDays.ONE_MONTH,
            )

        define_challenge = trigger("DefineAuthChallenge", "define")
        verify_challenge = trigger("VerifyAuthChallenge", "verify_code")

        create_challenge = trigger("CreateAuthChallenge", "create")
        create_challenge.add_environment("SES_FROM_ADDRESS", config.ses_from_address)
        create_challenge.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=[
                    self.format_arn(
                        service="ses",
                        resource="identity",
                        resource_name=config.ses_from_address,
                    )
                ],
            )
        )

        self.user_pool = cognito.UserPool(
            self,
            "PatientUserPool",
            user_pool_name=f"{config.stack_prefix}-patients",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=False)
            ),
            custom_attributes={
                "patient_id": cognito.StringAttribute(mutable=False),
                "signin_attempts": cognito.StringAttribute(mutable=True),
                "second_factor_hash": cognito.StringAttribute(mutable=True),
                "failed_attempts": cognito.StringAttribute(mutable=True),
            },
            lambda_triggers=cognito.UserPoolTriggers(
                define_auth_challenge=define_challenge,
                create_auth_challenge=create_challenge,
                verify_auth_challenge_response=verify_challenge,
            ),
            account_recovery=cognito.AccountRecovery.NONE,
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY
            ),
        )

        # Kept off the trigger's own role policy: the pool has to exist before
        # this can name it, and the trigger has to exist before the pool can
        # name the trigger, which CloudFormation will not deploy as one cycle.
        iam.Policy(
            self,
            "RecordSignInAttempts",
            roles=[create_challenge.role],
            statements=[
                iam.PolicyStatement(
                    actions=["cognito-idp:AdminUpdateUserAttributes"],
                    resources=[self.user_pool.user_pool_arn],
                )
            ],
        )

        client = self.user_pool.add_client(
            "PatientWebClient",
            user_pool_client_name=f"{config.stack_prefix}-web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                admin_user_password=False,
                user_password=False,
                user_srp=False,
                custom=True,
            ),
            prevent_user_existence_errors=True,
            auth_session_validity=cdk.Duration.minutes(5),
            access_token_validity=cdk.Duration.minutes(30),
            id_token_validity=cdk.Duration.minutes(30),
            refresh_token_validity=cdk.Duration.hours(8),
        )

        self.user_pool_client_id = client.user_pool_client_id

        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito user pool holding patient identities",
        )

        cdk.CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client_id,
            description="App client id used by the web frontend",
        )
