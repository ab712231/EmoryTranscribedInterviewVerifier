from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3

from .config import PortalConfig

SUMMARY_KEY_PREFIX = "summaries/"


class StorageStack(cdk.Stack):
    def __init__(self, scope, id, *, config: PortalConfig, **kwargs):
        super().__init__(scope, id, **kwargs)

        is_prod = config.env_name == "prod"
        removal = cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY

        self.summaries_key = kms.Key(
            self,
            "SummariesKey",
            alias=config.kms_key_alias,
            description=f"Encrypts patient interview summaries ({config.env_name})",
            enable_key_rotation=True,
            removal_policy=removal,
        )

        self.summaries_bucket = s3.Bucket(
            self,
            "SummariesBucket",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.summaries_key,
            bucket_key_enabled=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            event_bridge_enabled=True,
            removal_policy=removal,
            auto_delete_objects=not is_prod,
        )

        cdk.CfnOutput(
            self,
            "SummariesBucketName",
            value=self.summaries_bucket.bucket_name,
            description="S3 bucket holding interview summaries",
        )

        cdk.CfnOutput(
            self,
            "SummariesKeyArn",
            value=self.summaries_key.key_arn,
            description="KMS key encrypting interview summaries",
        )
