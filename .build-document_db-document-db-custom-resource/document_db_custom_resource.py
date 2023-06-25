"""Define the Lambda function for initializing the database."""
from enum import Enum
from typing import Any, List, Optional
from loguru import logger
import pymongo
from pymongo.database import Database
from pydantic import BaseModel, Field, validator
# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
    from ...construct_config import BasePydanticSettings
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_typing.events import CloudFormationCustomResourceEvent
except ImportError:
    from custom_resource_interface import CustomResourceInterface
    from construct_config import BasePydanticSettings
    LambdaContext = CloudFormationCustomResourceEvent = Any


class BuiltInMongoDBRoles(str, Enum):
    """Define the built-in MongoDB roles."""

    READ = "read"
    READ_WRITE = "readWrite"


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

    username: Optional[str] = Field(
        ...,
        description="The name of the database user.",
    )
    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.READ,
        description="The built-in MongoDB role to assign to the user.",
    )
    password_secret_name: Optional[str] = Field(
        ...,
        description="The name of the secret containing the user password.",
    )


class AdminDocumentDBSettings(BaseDocumentDBSettings):
    """Define the settings for the collections."""

    admin_username: str = Field(
        ...,
        description="The name of the database user.",
    )
    admin_user_password_secret_name: str = Field(
        ...,
        description="The name of the secret containing the admin user password.",
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


class DocumentDBSettings(AdminDocumentDBSettings):
    """Define the settings for the collections."""

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
    server_selection_timeout: int = Field(
        default=10,
        const=True,
        description="The number of seconds to wait for a server to be selected.",
    )


class DocumentDBCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: RuntimeDocumentDBSettings) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings.admin_user_password_secret_name)
        self._settings = settings
        self._mongo_client = self._run_operation_with_retry(self._connect_to_database, password)

    def _connect_to_database(self, password: str) -> pymongo.MongoClient:
        logger.info("Creating MongoDB client")
        settings = self._settings
        mongo_client = pymongo.MongoClient(
            f"mongodb://{settings.admin_username}:{password}@{settings.cluster_host_name}:{settings.cluster_port}/?tls=true&retryWrites=false",
            serverSelectionTimeoutMS=settings.server_selection_timeout,
        )
        logger.info(mongo_client.server_info())
        logger.info(f"Successfully connected to cluster at {settings.cluster_host_name}:{settings.cluster_port}")
        return mongo_client

    def _create_database(self) -> None:
        db = self._mongo_client[self._settings.db_name]
        for user in self._settings.user_config:
            self._run_operation_with_retry(self._create_user, db, user)
        self._run_operation_with_retry(self._create_collections, db)
        self._run_operation_with_retry(self._create_shards, db, self._mongo_client)
        self._run_operation_with_retry(self._create_indexes, db)


    def _update_database(self) -> None:
        raise NotImplementedError("Update operation not implemented.")


    def _delete_database(self) -> None:
        raise NotImplementedError("Delete operation not implemented.")

    def _create_user(self, db: Database, user: MongoDBUser) -> None:
        password = self.get_secret(user.password_secret_name)
        logger.info(f"Creating user: {user.username}")
        db.command({
            "createUser": user.username,
            "pwd": password,
            "roles": [
                {"role": user.role, "db": db.name},
            ],
        })

    def _create_collections(self, db: Database) -> None:
        for config in self._settings.collection_config:
            logger.info(f"Creating collection: {config.name}")
            db[config.name].insert_one({"_id": "dummy"})
            db[config.name].delete_one({"_id": "dummy"})

    def _create_shards(self, db: Database, client: pymongo.MongoClient) -> None:
        client.admin.command('enableSharding', db.name)
        for config in self._settings.collection_config:
            db.command({
                "shardCollection": f"{db.name}.{config.name}",
                "key": {"_id": "hashed"},
            })
            logger.info(f"Created shard for collection: {config.name}")

    def _create_indexes(self, db: Database) -> None:
        for config in self._settings.collection_config:
            for doc_field_name in config.fields_to_index:
                logger.info(f"Creating index for doc field: {doc_field_name} in collection: {config.name}")
                db[config.name].create_index(doc_field_name)
