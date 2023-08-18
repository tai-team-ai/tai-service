"""Define the runtime settings for the TAI API."""
from typing import Optional
from enum import Enum
from pydantic import Field, BaseSettings
# first imports are for local development, second imports are for deployment
try:
    from .taibackend.taitutors.llm_schemas import ModelName
except ImportError:
    from taibackend.taitutors.llm_schemas import ModelName

BACKEND_ATTRIBUTE_NAME = "tai_backend"


class AWSRegion(str, Enum):
    """Define valid AWS regions."""
    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"


class TaiApiSettings(BaseSettings):
    """Define the configuration model for the TAI API service."""

    message_archive_bucket_name: str = Field(
        default="llm-message-archive",
        description="The name of the student message archive bucket to store all student messages.",
    )
    openAI_api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the OpenAI API key.",
    )
    openAI_request_timeout: int = Field(
        default=30,
        description="The timeout for OpenAI requests.",
    )
    basic_model_name: ModelName = Field(
        default=ModelName.GPT_TURBO,
        description="The name of the model to use for the llm tutor for basic queries.",
    )
    large_context_model_name: ModelName = Field(
        default=ModelName.GPT_TURBO_LARGE_CONTEXT,
        description="The name of the model to use for the llm tutor for large context queries.",
    )
    advanced_model_name: ModelName = Field(
        default=ModelName.GPT_4,
        description="The name of the model to use for the llm tutor for advanced queries.",
    )
    search_service_api_url: str = Field(
        ...,
        description="The URL of the search service API.",
    )
    user_table_name: str = Field(
        default="tai-service-users",
        description="The name of the user table.",
    )
    user_table_partition_key: str = Field(
        default="id",
        description="The name of the user table partition key.",
    )
    user_table_sort_key: Optional[str] = Field(
        default=None,
        description="The name of the user table sort key.",
    )
    aws_default_region: AWSRegion = Field(
        default=AWSRegion.US_EAST_1,
        description="The AWS region for the DynamoDB table.",
    )
    dynamodb_host: Optional[str] = Field(
        default=None,
        description="The host for the DynamoDB table.",
    )
