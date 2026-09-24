from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_ses as ses

from .config import PortalConfig


def email_configuration_set_name(config: PortalConfig):
    return f"{config.stack_prefix}-participant-email"


class MessagingStack(cdk.Stack):
    def __init__(self, scope, id, *, config: PortalConfig, **kwargs):
        super().__init__(scope, id, **kwargs)

        configuration_set = ses.ConfigurationSet(
            self,
            "ParticipantEmail",
            configuration_set_name=email_configuration_set_name(config),
        )
        configuration_set.add_event_destination(
            "BouncesToEventBridge",
            destination=ses.EventDestination.event_bus(
                events.EventBus.from_event_bus_name(self, "DefaultEventBus", "default")
            ),
            events=[ses.EmailSendingEvent.BOUNCE],
        )

        if config.manage_ses_identity:
            ses.EmailIdentity(
                self,
                "MagicLinkSender",
                identity=ses.Identity.email(config.ses_from_address),
            )

            cdk.CfnOutput(
                self,
                "MagicLinkSenderAddress",
                value=config.ses_from_address,
                description=(
                    "SES sender identity for participant email. Check this inbox "
                    "for the AWS verification email and click the link before "
                    "signing in."
                ),
            )
        else:
            cdk.CfnOutput(
                self,
                "MagicLinkSenderAddress",
                value=config.ses_from_address,
                description=(
                    "SES sender identity for participant email. Verified out of "
                    "band by the account owner; this stack does not manage it."
                ),
            )
