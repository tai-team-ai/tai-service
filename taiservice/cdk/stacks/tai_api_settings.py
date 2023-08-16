"""Define settings for instantiating the TAI API."""
import os
from ...api.runtime_settings import TaiApiSettings
from ..constructs.construct_config import BaseDeploymentSettings

class DeploymentTaiApiSettings(BaseDeploymentSettings, TaiApiSettings):
    """Define the settings for instantiating the TAI API."""


TAI_API_SETTINGS = DeploymentTaiApiSettings(
    message_archive_bucket_name="llm-message-archive",
    openAI_api_key_secret_name=os.environ.get("OPENAI_API_KEY_SECRET_NAME"),
    search_service_api_url=os.environ.get("SEARCH_SERVICE_API_URL"),
)
