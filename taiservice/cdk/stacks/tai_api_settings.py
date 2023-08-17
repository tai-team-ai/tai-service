"""Define settings for instantiating the TAI API."""
import os
from aws_cdk import aws_dynamodb as dynamodb
from ...api.runtime_settings import TaiApiSettings
from ..stacks.tai_api_stack import DynamoDBSettings
from ..constructs.construct_config import BaseDeploymentSettings

class DeploymentTaiApiSettings(BaseDeploymentSettings, TaiApiSettings):
    """Define the settings for instantiating the TAI API."""


DYNAMODB_DEPLOYMENT_SETTINGS = DynamoDBSettings(
    table_name="tai-service-users",
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    partition_key=dynamodb.Attribute(
        name="user_id",
        type=dynamodb.AttributeType.STRING,
    ),
)


TAI_API_SETTINGS = DeploymentTaiApiSettings(
    message_archive_bucket_name="llm-message-archive",
    openAI_api_key_secret_name=os.environ.get("OPENAI_API_KEY_SECRET_NAME"),
    search_service_api_url=os.environ.get("SEARCH_SERVICE_API_URL"),
    user_table_name=DYNAMODB_DEPLOYMENT_SETTINGS.table_name,
    user_table_partition_key=DYNAMODB_DEPLOYMENT_SETTINGS.partition_key.name,
    user_table_sort_key=DYNAMODB_DEPLOYMENT_SETTINGS.sort_key.name,
)
