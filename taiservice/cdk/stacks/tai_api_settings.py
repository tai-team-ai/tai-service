"""Define settings for instantiating the TAI API."""
import os
from aws_cdk import aws_dynamodb as dynamodb
from tai_aws_account_bootstrap.stack_config_models import DeploymentType
from .deployment_settings import AWS_DEPLOYMENT_SETTINGS
from ...api.runtime_settings import TaiApiSettings, LogLevel
from ..stacks.tai_api_stack import DynamoDBSettings
from ..constructs.construct_config import BaseDeploymentSettings
from .search_service_settings import SEARCH_SERVICE_SETTINGS


class DeploymentTaiApiSettings(BaseDeploymentSettings, TaiApiSettings):
    """Define the settings for instantiating the TAI API."""


DYNAMODB_DEPLOYMENT_SETTINGS = DynamoDBSettings(
    table_name="tai-service-users",
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    partition_key=dynamodb.Attribute(
        name="id",
        type=dynamodb.AttributeType.STRING,
    ),
)

SORT_KEY_NAME = DYNAMODB_DEPLOYMENT_SETTINGS.sort_key.name if DYNAMODB_DEPLOYMENT_SETTINGS.sort_key else None
TAI_API_SETTINGS = DeploymentTaiApiSettings(
    message_archive_bucket_name="llm-message-archive",
    user_table_name=DYNAMODB_DEPLOYMENT_SETTINGS.table_name,
    user_table_partition_key=DYNAMODB_DEPLOYMENT_SETTINGS.partition_key.name,
    user_table_sort_key=SORT_KEY_NAME,
    log_level=LogLevel.DEBUG if AWS_DEPLOYMENT_SETTINGS.deployment_type == DeploymentType.DEV else LogLevel.INFO,
    doc_db_credentials_secret_name=os.environ.get("DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME"),
    doc_db_fully_qualified_domain_name=SEARCH_SERVICE_SETTINGS.doc_db_fully_qualified_domain_name,
    doc_db_database_name=SEARCH_SERVICE_SETTINGS.doc_db_database_name,
    doc_db_class_resource_collection_name=SEARCH_SERVICE_SETTINGS.doc_db_class_resource_collection_name,
)
