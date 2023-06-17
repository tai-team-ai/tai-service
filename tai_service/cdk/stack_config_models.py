from enum import Enum
import os
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, BaseSettings, Field, validator, Extra
from pygit2 import Repository
from aws_cdk import (
    Environment,
)


class AWSRegion(str, Enum):
    """Define AWS regions."""

    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"


class DeploymentType(str, Enum):
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
    aws_environment: Optional[Environment] = Field(
        default=None,
        env="AWS_ENVIRONMENT",
        description="The AWS environment to deploy to.",
    )
    deployment_type: DeploymentType = Field(
        default=DeploymentType.DEV,
        env="DEPLOYMENT_TYPE",
        description="The deployment type. This is used to isolate stacks from various environments.",
    )
    aws_access_key_id: str = Field(
        default=None,
        env="AWS_ACCESS_KEY_ID",
        description="The AWS access key ID to use for deployment.",
    )
    aws_secret_access_key: str = Field(
        default=None,
        env="AWS_SECRET_ACCESS_KEY",
        description="The AWS secret access key to use for deployment.",
    )

    class Config:
        """Define configuration for AWS deployment settings."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        allow_population_by_field_name = True

    @validator("aws_environment")
    def initialize_environment(cls, env: Optional[Environment], values: dict) -> Environment:
        """Initialize the AWS environment."""
        if env is None:
            return Environment(
                account=values["aws_deployment_account_id"],
                region=values["aws_region"],
            )
        if env.account != values["aws_deployment_account_id"]:
            raise ValueError(
                f"Environment account {env.account} does not match deployment account {values['aws_deployment_account_id']}."
            )
        if env.region != values["aws_region"]:
            raise ValueError(
                f"Environment region {env.region} does not match deployment region {values['aws_region']}."
            )

    @validator("staging_stack_suffix")
    def initialize_staging_stack_suffix(cls, suffix: str) -> str:
        """Initialize the staging stack suffix."""
        if suffix:
            return suffix
        return ""


class StackConfigBaseModel(BaseModel):
    """Define the base model for stack configuration."""

    stack_id: str = Field(
        ...,
        description="The ID of the stack.",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=255,
        description="The description of the stack.",
    )
    stack_name: str = Field(
        ...,
        description="The name of the stack/service.",
    )
    deployment_settings: AWSDeploymentSettings = Field(
        ...,
        description="The AWS deployment settings.",
    )
    termination_protection: bool = Field(
        default=True,
        description="Whether or not to enable termination protection for the stack.",
    )
    duplicate_stack_for_development: bool = Field(
        default=True,
        description="""
            Whether or not to duplicate the stack for development. This will rename all 
            resources to include the staging stack suffix.
        """,
    )
    tags: dict = Field(
        default_factory=dict,
        description="The tags to apply to the stack.",
    )

    class Config:
        """Define configuration for stack configuration."""

        arbitrary_types_allowed = True
        validate_assignment = True
        extra = Extra.forbid

    @validator("resource_name", "stack_id")
    def add_suffix_to_names(cls, name: str, values: dict) -> str:
        """Add the staging stack suffix to the resource name."""
        branch_name = Repository(os.getcwd()).head.shorthand
        branch_name = re.sub(r"[^a-zA-Z0-9]", '-', branch_name)
        is_main = branch_name == "main" or branch_name == "master" or \
            branch_name == "production" or branch_name == "prod" or branch_name == "dev"
        if is_main or not values["duplicate_stack_for_development"]:
            return name
        return f"{name}-{branch_name}"

    @validator("termination_protection")
    def validate_on_if_prod(cls, termination_protection: bool, values: dict) -> bool:
        """Validate that termination protection is enabled if the deployment type is prod."""
        settings: AWSDeploymentSettings = values["deployment_settings"]
        if settings.deployment_type == DeploymentType.PROD:
            assert termination_protection is True, "Termination protection must be enabled for prod deployments."
        return termination_protection

    @validator("tags")
    def tags_include_blame_tag(cls, tags: dict) -> dict:
        """Include the blame tag in the tags."""
        for key in tags.keys():
            if key == "blame":
                return tags
        raise ValueError("A blame tag must be included in the tags.")

    @validator("termination_protection")
    def ensure_termination_protection_for_prod(cls, termination_protection: bool, values: dict) -> bool:
        """Ensure termination protection is enabled for production deployments."""
        if values["deployment_type"] == DeploymentType.PROD:
            if not termination_protection:
                logger.warning(
                    "Termination protection is disabled. Enabling termination protection for production deployment."
                )
            return True
        return termination_protection
