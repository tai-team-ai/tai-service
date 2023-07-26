"""Define helpers for CDK stacks."""
from enum import Enum
from aws_cdk import (
    Tags,
)
import boto3
from constructs import Construct
from taiservice.cdk.stacks.stack_config_models import AWSDeploymentSettings


class Permissions(str, Enum):
    """Define permissions for AWS resources."""

    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


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
    credentials = {}
    if deployment_settings.aws_access_key_id and deployment_settings.aws_secret_access_key:
        credentials = {
            "aws_access_key_id": deployment_settings.aws_access_key_id,
            "aws_secret_access_key": deployment_settings.aws_secret_access_key,
        }

    client = boto3.client(
        "secretsmanager",
        region_name=deployment_settings.aws_region,
        **credentials,
    )
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]


def get_secret_arn_from_name(deployment_settings: AWSDeploymentSettings, secret_name: str) -> str:
    """Get the ARN of a secret from its name.

    Args:
        deployment_settings (AWSDeploymentSettings): The deployment settings for the stack.
        secret_name (str): The name of the secret to get the ARN for.

    Returns:
        str: The ARN of the secret.
    """
    credentials = {}
    if deployment_settings.aws_access_key_id and deployment_settings.aws_secret_access_key:
        credentials = {
            "aws_access_key_id": deployment_settings.aws_access_key_id,
            "aws_secret_access_key": deployment_settings.aws_secret_access_key,
        }

    client = boto3.client(
        "secretsmanager",
        region_name=deployment_settings.aws_region,
        **credentials,
    )
    response = client.describe_secret(SecretId=secret_name)
    return response["ARN"]
