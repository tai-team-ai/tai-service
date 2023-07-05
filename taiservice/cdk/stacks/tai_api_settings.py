"""Define settings for instantiating the TAI API."""
import os
from ...api.runtime_settings import TaiApiSettings
from ..constructs.construct_config import BaseDeploymentSettings
from .search_databases_settings import DOCUMENT_DB_SETTINGS, PINECONE_DB_SETTINGS

class DeploymentTaiApiSettings(BaseDeploymentSettings, TaiApiSettings):
    """Define the settings for instantiating the TAI API."""


TAI_API_SETTINGS = DeploymentTaiApiSettings(
    doc_db_credentials_secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
    doc_db_username_secret_key="username",
    doc_db_password_secret_key="password",
    doc_db_fully_qualified_domain_name="", # this gets set at runtime in app.py
    doc_db_port=DOCUMENT_DB_SETTINGS.cluster_port,
    doc_db_database_name=DOCUMENT_DB_SETTINGS.db_name,
    doc_db_class_resource_collection_name=DOCUMENT_DB_SETTINGS.collection_config[0].name,
    doc_db_class_resource_chunk_collection_name=DOCUMENT_DB_SETTINGS.collection_config[1].name,
    pinecone_db_api_key_secret_name=PINECONE_DB_SETTINGS.api_key_secret_name,
    pinecone_db_environment=PINECONE_DB_SETTINGS.environment,
    pinecone_db_index_name=PINECONE_DB_SETTINGS.indexes[0].name,
    openAI_api_key_secret_name=os.environ.get("OPENAI_API_KEY_SECRET_NAME"),
)
