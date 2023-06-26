"""Define settings for the document database."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator

# first imports are for local development, second imports are for deployment
try:
    from tai_service.cdk.constructs.construct_config import BasePydanticSettings
except ImportError:
    from construct_config import BasePydanticSettings


class BuiltInMongoDBRoles(str, Enum):
    """Define the built-in MongoDB roles."""

    READ = "read"
    READ_WRITE = "readWrite"
    ROOT = "root"


class BaseDocumentDBSettings(BasePydanticSettings):
    """Define the base settings for the document database."""

    cluster_name: str = Field(
        ...,
        description="The name of the cluster.",
    )
    cluster_port: int = Field(
        default=27017,
        description="The port number of the cluster.",
    )
    db_name: str = Field(
        ...,
        description="The name of the database.",
    )

    class Config:
        """Define the Pydantic config."""

        env_prefix = "DOC_DB_"


class MongoDBUser(BaseModel):
    """Define the settings for the collections."""

    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.READ,
        description="The built-in MongoDB role to assign to the user.",
    )
    secret_name: str = Field(
        ...,
        description="The name of the secret containing the user password.",
    )
    username_secret_field_name: str = Field(
        default="username",
        description="The name of the field containing the username.",
    )
    password_secret_field_name: str = Field(
        default="password",
        description="The name of the field in containing the password.",
    )


class CollectionConfig(BaseModel):
    """Define the settings for the collections."""

    name: str = Field(
        ...,
        max_length=45,
        description="Name of the collection.",
    )
    fields_to_index: Optional[list[str]] = Field(
        default=None,
        description="The fields to index for the collection.",
    )
    shard_key: Optional[str] = Field(
        default=None,
        description="The field to use as the shard key.",
    )


class DocumentDBSettings(MongoDBUser, BaseDocumentDBSettings):
    """Define the settings for the collections."""

    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.ROOT,
        const=True,
        description="The built-in MongoDB role to assign to the user.",
    )
    collection_config: Optional[List[CollectionConfig]] = Field(
        default=None,
        description="The indexes to create for each collection.",
    )
    user_config: Optional[List[MongoDBUser]] = Field(
        ...,
        max_items=3,
        min_items=1,
        description="The users to create for the database.",
    )

    @validator("collection_config")
    def ensure_no_duplicate_indexes(cls, collections: Optional[List[CollectionConfig]]) -> Optional[CollectionConfig]:
        """Ensure that there are no duplicate indexes."""
        if collections is None:
            return None
        col_names = [collection.name for collection in collections]
        if len(col_names) != len(set(col_names)):
            raise ValueError("Collections must have unique names.")
        return collections


class RuntimeDocumentDBSettings(DocumentDBSettings):
    """Define runtime settings for the document database."""

    cluster_host_name: str = Field(
        ...,
        description="""The fully qualified domain name of the cluster.
            Note, this is not the same as the cluster name.
            Examples:
                cluster_host_name: cluster-1234567890.us-east-1.docdb.amazonaws.com
                cluster_name: cluster-1234567890
        """,
    )
    server_selection_timeout_MS: int = Field(
        default=10000,
        description="The number of milliseconds to wait for a server to be selected.",
    )
