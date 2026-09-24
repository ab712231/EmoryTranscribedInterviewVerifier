import os

import aws_cdk as cdk

from portal.api_stack import ApiStack
from portal.auth_stack import AuthStack
from portal.config import load_config
from portal.messaging_stack import MessagingStack
from portal.storage_stack import StorageStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"
config = load_config(env_name)

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=config.region,
)

common = {
    "env": env,
    "tags": {"project": "patient-portal", "environment": config.env_name},
}

storage = StorageStack(
    app,
    f"{config.stack_prefix}-Storage",
    config=config,
    description=f"Patient portal summaries storage ({config.env_name})",
    **common,
)

messaging = MessagingStack(
    app,
    f"{config.stack_prefix}-Messaging",
    config=config,
    description=f"Patient portal email delivery ({config.env_name})",
    **common,
)

auth = AuthStack(
    app,
    f"{config.stack_prefix}-Auth",
    config=config,
    description=f"Patient portal authentication ({config.env_name})",
    **common,
)

api = ApiStack(
    app,
    f"{config.stack_prefix}-Api",
    config=config,
    description=f"Patient portal API ({config.env_name})",
    summaries_bucket=storage.summaries_bucket,
    summaries_key=storage.summaries_key,
    user_pool=auth.user_pool,
    user_pool_client_id=auth.user_pool_client_id,
    **common,
)
api.node.add_dependency(messaging)

app.synth()
