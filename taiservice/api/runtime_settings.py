"""Define the runtime settings for the TAI API."""
from pydantic import Field, BaseSettings
# first imports are for local development, second imports are for deployment
try:
    from .taibackend.taitutors.llm import ModelName
except ImportError:
    from taibackend.taitutors.llm import ModelName

BACKEND_ATTRIBUTE_NAME = "tai_backend"


class TaiApiSettings(BaseSettings):
    """Define the configuration model for the TAI API service."""

    message_archive_bucket_name: str = Field(
        ...,
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
