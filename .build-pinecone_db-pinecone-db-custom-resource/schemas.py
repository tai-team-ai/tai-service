"""Define schemas used in the package."""
from enum import Enum
from numbers import Number
import json
from typing import Optional, Sequence
from pydantic import BaseSettings, Field, root_validator, validator


DOC_DB_ENVIRONMENT_PREFIX = "DOC_DB_"

class PineConeEnvironment(str, Enum):
    """Define the environments for the Pinecone project."""

    EAST_1 = "us-east-1-aws"

class BasePydanticSettings(BaseSettings):
    """Define the base settings for the package."""

    def dict(self, *args, **kwargs):
        """Override the dict method to convert nested, dicts, sets and sequences to JSON."""
        output = super().dict(*args, **kwargs)
        new_output = {}
        for key, value in output.items():
            if hasattr(self.Config, "env_prefix"):
                key = self.Config.env_prefix + key
            if isinstance(value, dict) or isinstance(value, list) or isinstance(value, set) or isinstance(value, tuple):
                value = json.dumps(value)
            key = key.upper()
            new_output[key] = value
        return new_output

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
    read_only_user_password_secret_name: Optional[str] = Field(
        default=None,
        description="The name of the secret containing the read-only user password.",
    )

    @validator("read_only_user_password_secret_name")
    def ensure_user_name(cls, password_secret_name: str, values: dict) -> str:
        """Ensure that a secret name is provided."""
        if password_secret_name:
            assert values.get("read_only_user_name"), "Please provide a user name."
        return password_secret_name


class ReadWriteDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    read_write_user_name: Optional[str] = Field(
        default=None,
        description="The name of the database user with read/write permissions.",
    )
    read_write_user_password_secret_name: Optional[str] = Field(
        default=None,
        description="The name of the secret containing the read/write user password.",
    )

    @validator("read_write_user_password_secret_name")
    def ensure_user_name(cls, password_secret_name: str, values: dict) -> str:
        """Ensure that a secret name is provided."""
        if password_secret_name:
            assert values.get("read_write_user_name"), "Please provide a user name."
        return password_secret_name


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

    class Config:
        """Define the Pydantic config."""

        env_prefix = "PINECONE_DB_"
