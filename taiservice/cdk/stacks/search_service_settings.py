"""Define settings for instantiating search databases."""
import os
from dotenv import load_dotenv
from tai_aws_account_bootstrap.stack_config_models import DeploymentType
from taiservice.cdk.constructs.customresources.document_db.settings import (
    DocumentDBSettings,
    CollectionConfig,
    MongoDBUser,
    BuiltInMongoDBRoles,
)
from taiservice.cdk.constructs.customresources.pinecone_db.pinecone_db_custom_resource import (
    PodType,
    PodSize,
    DistanceMetric,
    PineconeIndexConfig,
    PineconeDBSettings,
)
from taiservice.searchservice.runtime_settings import SearchServiceSettings, LogLevel
from .deployment_settings import AWS_DEPLOYMENT_SETTINGS
from ..constructs.construct_config import BaseDeploymentSettings


class DeploymentTaiApiSettings(BaseDeploymentSettings, SearchServiceSettings):
    """Define the settings for instantiating the TAI API."""


INDEXES = [
    PineconeIndexConfig(
        name="tai-index",
        dimension=1536,
        metric=DistanceMetric.DOT_PRODUCT,
        pod_instance_type=PodType.S1,
        pod_size=PodSize.X1,
        pods=1,
        replicas=1,
    )
]
PINECONE_DB_SETTINGS = PineconeDBSettings(indexes=INDEXES)

COLLECTION_CONFIG = [
    CollectionConfig(
        name="class_resource",
        fields_to_index=["class_id", "resource_id"],
    ),
    CollectionConfig(
        name="class_resource_chunk",
        fields_to_index=["class_id", "resource_id", "chunk_id"],
    ),
]
load_dotenv()
USER_CONFIG = [
    MongoDBUser(
        secret_name=os.environ.get("DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME"),
        role=BuiltInMongoDBRoles.READ,
    ),
    MongoDBUser(
        secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
        role=BuiltInMongoDBRoles.READ_WRITE,
    ),
]
DOCUMENT_DB_SETTINGS = DocumentDBSettings(
    secret_name=os.environ.get("DOC_DB_ADMIN_USER_PASSWORD_SECRET_NAME"),
    cluster_name="tai-service",
    collection_config=COLLECTION_CONFIG,
    db_name="class_resources",
    user_config=USER_CONFIG,
)

SEARCH_SERVICE_SETTINGS = DeploymentTaiApiSettings(
    pinecone_db_api_key_secret_name=PINECONE_DB_SETTINGS.api_key_secret_name,
    pinecone_db_environment=PINECONE_DB_SETTINGS.environment,
    pinecone_db_index_name=PINECONE_DB_SETTINGS.indexes[0].name,
    doc_db_credentials_secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
    doc_db_username_secret_key="username",
    doc_db_password_secret_key="password",
    doc_db_fully_qualified_domain_name="", # this gets set at runtime in app.py
    doc_db_port=DOCUMENT_DB_SETTINGS.cluster_port,
    doc_db_database_name=DOCUMENT_DB_SETTINGS.db_name,
    doc_db_class_resource_collection_name=DOCUMENT_DB_SETTINGS.collection_config[0].name,
    doc_db_class_resource_chunk_collection_name=DOCUMENT_DB_SETTINGS.collection_config[1].name,
    openAI_api_key_secret_name=os.environ.get("OPENAI_API_KEY_SECRET_NAME"),
    cold_store_bucket_name="tai-service-class-resource-cold-store",
    documents_to_index_queue="tai-service-documents-to-index-queue",
    log_level=LogLevel.DEBUG if AWS_DEPLOYMENT_SETTINGS.deployment_type == DeploymentType.DEV else LogLevel.INFO,
)
