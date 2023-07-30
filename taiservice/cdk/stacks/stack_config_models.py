from enum import Enum
import os
import re
from typing import Optional, Callable

from pydantic import BaseModel, BaseSettings, Field, validator, Extra, root_validator
from pygit2 import Repository
from aws_cdk import (
    Environment,
    RemovalPolicy,
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
        env="AWS_DEFAULT_REGION",
        description="The AWS region to deploy to.",
    )
    aws_environment: Optional[Environment] = Field(
        default=None,
        env="AWS_ENVIRONMENT",
        description="The AWS environment to deploy to.",
    )
    deployment_type: DeploymentType = Field(
        default=DeploymentType.PROD,
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
            region: AWSRegion = values.get("aws_region")
            return Environment(
                account=values.get("aws_deployment_account_id"),
                region=region.value,
            )
        if env.account != values["aws_deployment_account_id"]:
            raise ValueError(
                f"Environment account {env.account} does not match deployment account {values['aws_deployment_account_id']}."
            )
        if env.region != values["aws_region"]:
            raise ValueError(
                f"Environment region {env.region} does not match deployment region {values['aws_region']}."
            )
        raise ValueError("AWS Environment must be initialized with account and region.")


class StackConfigBaseModel(BaseModel):
    """Define the base model for stack configuration."""

    deployment_settings: AWSDeploymentSettings = Field(
        ...,
        description="The AWS deployment settings.",
    )
    duplicate_stack_for_development: bool = Field(
        default=True,
        description="""
            Whether or not to duplicate the stack for development. This will rename all 
            resources to include the staging stack suffix.
        """,
    )
    stack_suffix: str = Field(
        default="",
        description="The stack suffix to append to resources in the stack if duplicate_stack_for_development is enabled.",
    )
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
    termination_protection: bool = Field(
        default=True,
        description="Whether or not to enable termination protection for the stack.",
    )
    tags: dict = Field(
        default_factory=dict,
        description="The tags to apply to the stack.",
    )
    removal_policy: RemovalPolicy = Field(
        default=RemovalPolicy.RETAIN,
        description="The removal policy for the stack.",
    )
    namer: Callable[[str], str] = Field(
        default=lambda name: name,
        description="The function to use to name resources in the stack.",
    )

    @root_validator()
    def initialize_namer(cls, values: dict) -> dict:
        """Initialize the namer."""
        namer = values["namer"]
        stack_name = values["stack_name"]
        namer = lambda name: f"{stack_name}-{name}"
        values["namer"] = namer
        return values

    class Config:
        """Define configuration for stack configuration."""

        arbitrary_types_allowed = True
        validate_assignment = True
        extra = Extra.forbid

    @root_validator()
    def create_suffix(cls, values: dict) -> dict:
        """Create the stack suffix."""
        branch_name = Repository(os.getcwd()).head.shorthand
        branch_name = re.sub(r"[^a-zA-Z0-9]", '-', branch_name)
        is_main = branch_name == "main" or branch_name == "master" or \
            branch_name == "production" or branch_name == "prod"
        deploy_settings: AWSDeploymentSettings = values["deployment_settings"]
        if is_main or not values["duplicate_stack_for_development"]:
            if deploy_settings.deployment_type == DeploymentType.DEV:
                values["stack_suffix"] = f"-{deploy_settings.deployment_type.value}"
            return values
        stack_suffix = f"-{branch_name[:10]}-{deploy_settings.deployment_type.value}"
        # Remove any special characters from the stack suffix
        stack_suffix = re.sub(r"[^a-zA-Z0-9-]", '-', stack_suffix)
        # Remove any trailing dashes from the stack suffix
        stack_suffix = re.sub(r"[-]+$", '', stack_suffix)
        values["stack_suffix"] = stack_suffix
        values["stack_name"] = f"{values['stack_name']}{stack_suffix}"
        values["stack_id"] = f"{values['stack_id']}{stack_suffix}"
        return values

    @validator("termination_protection")
    def validate_on_if_prod(cls, termination_protection: bool, values: dict) -> bool:
        """Validate that termination protection is enabled if the deployment type is prod."""
        settings: AWSDeploymentSettings = values["deployment_settings"]
        if settings.deployment_type == DeploymentType.PROD:
            assert termination_protection is True, "Termination protection must be enabled for prod deployments."
        return termination_protection

    @validator("removal_policy")
    def validate_retain_if_prod(cls, removal_policy: RemovalPolicy, values: dict) -> RemovalPolicy:
        """Validate that the removal policy is retain if the deployment type is prod."""
        settings: AWSDeploymentSettings = values["deployment_settings"]
        if settings.deployment_type == DeploymentType.PROD:
            assert removal_policy == RemovalPolicy.RETAIN, "Removal policy must be retain for prod deployments."
        return removal_policy

    @validator("tags")
    def tags_include_blame_tag(cls, tags: dict) -> dict:
        """Include the blame tag in the tags."""
        for key in tags.keys():
            if key == "blame":
                return tags
        raise ValueError("A blame tag must be included in the tags.")
