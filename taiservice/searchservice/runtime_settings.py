from pathlib import Path
from pydantic import Field, BaseSettings
from .backend.databases.pinecone_db import Environment as PineconeEnvironment


BACKEND_ATTRIBUTE_NAME = "tai_backend"


class TaiApiSettings(BaseSettings):
    """Define the configuration model for the TAI API service."""

    pinecone_db_api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the Pinecone API key.",
    )
    pinecone_db_environment: PineconeEnvironment = Field(
        ...,
        description="The environment of the pinecone db.",
    )
    pinecone_db_index_name: str = Field(
        ...,
        description="The name of the pinecone index.",
    )
    doc_db_credentials_secret_name: str = Field(
        ...,
        description="The name of the secret containing the document database credentials.",
    )
    doc_db_username_secret_key: str = Field(
        default="username",
        const=True,
        description="The name of the secret key containing the document database username.",
    )
    doc_db_password_secret_key: str = Field(
        default="password",
        const=True,
        description="The name of the secret key containing the document database password.",
    )
    doc_db_fully_qualified_domain_name: str = Field(
        ...,
        description="The fully qualified domain name of the TAI API service.",
    )
    doc_db_port: int = Field(
        ...,
        description="The port of the TAI API service.",
    )
    doc_db_database_name: str = Field(
        ...,
        description="The name of the document db.",
    )
    doc_db_class_resource_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db for class resources.",
    )
    doc_db_class_resource_chunk_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db for class resource chunks.",
    )
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
    openAI_batch_size: int = Field(
        default=50,
        description="The batch size for OpenAI requests.",
    )
    nltk_data: str = Field(
        default="/var/task/nltk_data",
        description="The path to the nltk data.",
    )
    transformers_cache: str = Field(
        default="/tmp/transformers_cache",
        description="The path to the transformers cache.",
    )
    cold_store_bucket_name: str = Field(
        ...,
        description="The name of the cold store bucket.",
    )
    chrome_driver_path: Path = Field(
        default=Path("/var/task/chromedriver"),
        description="The path to the chrome driver.",
    )
    class_resource_processing_timeout: int = Field(
        default=240,
        description="The timeout for class resource processing.",
    )