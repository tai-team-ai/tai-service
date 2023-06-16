from enum import Enum

from pydantic import BaseSettings, Field


class AWSRegion(str, Enum):
    """Define AWS regions."""

    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"


class AWSDeploymentEnvironment(str, Enum):
    """Define deployment environments."""

    DEV = "dev"
    PROD = "prod"


class AWSDeploymentSettings(BaseSettings):
    """Define AWS deployment settings."""

    aws_deployment_account_id: str = Field(
        ...,
        env="AWS_DEPLOYMENT_ACCOUNT_ID",
        description="The AWS account ID to deploy to.",
    )
    aws_region: AWSRegion = Field(
        default=AWSRegion.US_EAST_1,
        env="AWS_REGION",
        description="The AWS region to deploy to.",
    )
    aws_deployment_environment: AWSDeploymentEnvironment = Field(
        default=AWSDeploymentEnvironment.DEV,
        env="AWS_DEPLOYMENT_ENVIRONMENT",
        description="The AWS deployment environment. These are used to isolate stacks from various environments.",
    )
    
