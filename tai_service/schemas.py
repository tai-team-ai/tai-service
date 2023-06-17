"""Define schemas used in the package."""
import json
from typing import Sequence
from pydantic import BaseSettings, Field


class BasePydanticSettings(BaseSettings):
    """Define the base settings for the package."""

    def dict(self, *args, **kwargs):
        """Override the dict method to convert nested, dicts, sets and sequences to JSON."""
        output = super().dict(*args, **kwargs)
        for key, value in output.items():
            if isinstance(value, dict) or isinstance(value, Sequence) or isinstance(value, set):
                output[key] = json.dumps(value)
        return output

    class Config:
        """Define the Pydantic config."""

        use_enum_values = True
        env_file = ".env"
        env_file_encoding = "utf-8"


class BaseDocumentDBSettings(BasePydanticSettings):
    """Define the base settings for the document database."""

    cluster_name: str = Field(
        ...,
        env="CLUSTER_HOST_NAME",
        description="The fully qualified domain name of the cluster.",
    )
    cluster_port: int = Field(
        ...,
        env="CLUSTER_PORT",
        description="The port number of the cluster.",
    )
    db_name: str = Field(
        ...,
        env="DB_NAME",
        description="The name of the database.",
    )
    collection_names: list[str] = Field(
        ...,
        env="COLLECTION_NAMES",
        description="The names of the collections in the database.",
    )
    server_selection_timeout: int = Field(
        default=10,
        const=True,
        env="SERVER_SELECTION_TIMEOUT",
        description="The number of seconds to wait for a server to be selected.",
    )


class ReadOnlyDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    read_only_user_name: str = Field(
        default="read_only_user",
        const=True,
        env="READ_ONLY_USER_NAME",
        description="The name of the database user with read-only permissions.",
    )
    read_only_user_password_secret_name: str = Field(
        ...,
        env="READ_ONLY_USER_PASSWORD_SECRET_NAME",
        description="The name of the secret containing the read-only user password.",
    )


class ReadWriteDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    read_write_user_name: str = Field(
        default="read_write_user",
        const=True,
        env="READ_WRITE_USER_NAME",
        description="The name of the database user with read/write permissions.",
    )
    read_write_user_password_secret_name: str = Field(
        ...,
        env="READ_WRITE_USER_PASSWORD_SECRET_NAME",
        description="The name of the secret containing the read/write user password.",
    )


class AdminDocumentDBSettings(ReadOnlyDocumentDBSettings, ReadWriteDocumentDBSettings):
    """Define the settings for the collections."""

    admin_user_name: str = Field(
        ...,
        env="ADMIN_USER_NAME",
        description="The name of the database user.",
    )
    admin_user_password_secret_name: str = Field(
        ...,
        env="ADMIN_USER_PASSWORD_SECRET_NAME",
        description="The name of the secret containing the admin user password.",
    )


class BasePineconeDBSettings(BasePydanticSettings):
    """Define the settings for initializing the Pinecone database."""

    pinecone_api_key_secret_name: str = Field(
        ...,
        env="PINECONE_API_KEY_SECRET_NAME",
        description="The name of the secret containing the Pinecone API key.",
    )
    pinecone_environment: str = Field(
        ...,
        env="PINECONE_ENVIRONMENT",
        description="The environment to use for the Pinecone project.",
    )
