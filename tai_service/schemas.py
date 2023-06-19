"""Define schemas used in the package."""
from enum import Enum
import json
from typing import Optional, Sequence
from pydantic import BaseSettings, Field, validator


DOC_DB_ENVIRONMENT_PREFIX = "DOC_DB_"

class PineConeEnvironment(Enum):
    """Define the environments for the Pinecone project."""

    EAST_1 = "us-east-1-aws"

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
        description="The fully qualified domain name of the cluster.",
    )
    cluster_port: int = Field(
        ...,
        description="The port number of the cluster.",
    )
    db_name: str = Field(
        ...,
        description="The name of the database.",
    )
    collection_names: list[str] = Field(
        ...,
        description="The names of the collections in the database.",
    )
    server_selection_timeout: int = Field(
        default=10,
        const=True,
        description="The number of seconds to wait for a server to be selected.",
    )

    class Config:
        """Define the Pydantic config."""

        env_prefix = DOC_DB_ENVIRONMENT_PREFIX


class ReadOnlyDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    read_only_user_name: Optional[str] = Field(
        default=None,
        description="The name of the database user with read-only permissions.",
    )
    read_only_user_password_secret_name: str = Field(
        default=None,
        description="The name of the secret containing the read-only user password.",
    )

    @validator("read_only_user_password_secret_name")
    def ensure_secret_if_user_name_provided(cls, secret_name: str, values: dict) -> str:
        """Ensure that a secret name is provided if a user name is provided."""
        if secret_name and values.get("read_only_user_name"):
            return secret_name
        raise ValueError(
            "A secret name must be provided if a read-only user name is provided."
        )


class ReadWriteDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    read_write_user_name: Optional[str] = Field(
        default=None,
        description="The name of the database user with read/write permissions.",
    )
    read_write_user_password_secret_name: str = Field(
        default=None,
        description="The name of the secret containing the read/write user password.",
    )

    @validator("read_write_user_password_secret_name")
    def ensure_secret_if_user_name_provided(cls, secret_name: str, values: dict) -> str:
        """Ensure that a secret name is provided if a user name is provided."""
        if secret_name and values.get("read_write_user_name"):
            return secret_name
        raise ValueError(
            "A secret name must be provided if a read/write user name is provided."
        )


class AdminDocumentDBSettings(ReadOnlyDocumentDBSettings, ReadWriteDocumentDBSettings):
    """Define the settings for the collections."""

    admin_user_name: str = Field(
        ...,
        description="The name of the database user.",
    )
    admin_user_password_secret_name: str = Field(
        ...,
        description="The name of the secret containing the admin user password.",
    )


class BasePineconeDBSettings(BasePydanticSettings):
    """Define the settings for initializing the Pinecone database."""

    api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the Pinecone API key.",
    )
    environment: PineConeEnvironment = Field(
        ...,
        description="The environment to use for the Pinecone project.",
    )
    index_names: list[str] = Field(
        ...,
        description="The names of the indexes in the Pinecone environment.",
    )

    class Config:
        """Define the Pydantic config."""

        env_prefix = "PINECONE_DB_"
