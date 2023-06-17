"""Define helpers for CDK stacks."""
from aws_cdk import Tags
from constructs import Construct
from tai_service.cdk.stack_config_models import AWSDeploymentSettings

def add_tags(scope: Construct, tags: dict):
    """Add tags to a CDK stack.

    Args:
        scope (cdk.Construct): The CDK stack to add tags to.
        tags (dict): The tags to add to the stack.
    """
    for key, value in tags.items():
        Tags.of(scope).add(key, value)

def retrieve_secret(deployment_settings: AWSDeploymentSettings, secret_name: str) -> str:
    """Retrieve a secret from AWS Secrets Manager.

    Args:
        deployment_settings (AWSDeploymentSettings): The deployment settings for the stack.
        secret_name (str): The name of the secret to retrieve.

    Returns:
        str: The value of the secret.
    """
    credentials = {
        "access_key_id": deployment_settings.
    }