"""Define the Lambda function for initializing the database."""
from enum import Enum
import json
from typing import Any
from loguru import logger
import pymongo
from pymongo.database import Database
from pydantic import BaseModel, Field, validator
# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
    from tai_service.schemas import AdminDocumentDBSettings
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_typing.events import CloudFormationCustomResourceEvent
except ImportError:
    from custom_resource_interface import CustomResourceInterface
    from schemas import AdminDocumentDBSettings
    LambdaContext = CloudFormationCustomResourceEvent = Any



class BuiltInMongoDBRoles(Enum):
    """Define the built-in MongoDB roles."""

    READ = "read"
    READ_WRITE = "readWrite"


class DocumentDBConfig(BaseModel):
    """Define the settings for the collections."""

    collection_indexes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="The indexes to create for each collection.",
    )
    db_settings: AdminDocumentDBSettings = Field(
        ...,
        description="The settings for the database.",
    )

    @validator("collection_indexes")
    def ensure_index_names_is_subset_of_settings(cls, col_indexes: dict[str, list[str]], values: dict[str, Any]) -> dict[str, list[str]]:
        """Ensure that the index names are a subset of the collection names."""
        fields_to_index = set(col_indexes.keys())
        db_settings: AdminDocumentDBSettings = values["db_settings"]
        collection_names = set(db_settings.collection_names)
        if fields_to_index.issubset(collection_names):
            return col_indexes
        raise ValueError(
            "Index names used for creating indexes must be a subset of the index names in the settings. " \
            f"Index names used for creating indexes: {fields_to_index}. Index names in settings: {collection_names}."
        )


def lambda_handler(event: CloudFormationCustomResourceEvent, context: LambdaContext) -> None:
    """
    Run the database operation.
    
    This function is invoked by the CloudFormation custom resource. It is responsible for
    running CRUD operations on the database by retrieving admin credentials from Secrets Manager and
    creating shards, collections, and indexes for the database.

    Currently, only create operations are supported, but this function could be extended
    to include all CRUD operations.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    db_config = DocumentDBConfig()
    custom_resource = DocumentDBCustomResource(event, context, db_config)
    custom_resource.execute_crud_operation()


class DocumentDBCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, config: DocumentDBConfig) -> None:
        super().__init__(event, context)
        password = self.get_secret(config.db_settings.admin_user_password_secret_name)
        self._config = config
        self._settings = config.db_settings
        self._mongo_client = self._run_operation_with_retry(self._connect_to_database, password)

    def _connect_to_database(self, password: str) -> pymongo.MongoClient:
        logger.info("Creating MongoDB client")
        settings = self._settings
        mongo_client = pymongo.MongoClient(
            f"mongodb://{settings.admin_user_name}:{password}@{settings.cluster_host_name}:{settings.cluster_port}/?tls=true&retryWrites=false",
            serverSelectionTimeoutMS=settings.server_selection_timeout,
        )
        logger.info(mongo_client.server_info())
        logger.info(f"Successfully connected to cluster at {settings.cluster_host_name}:{settings.cluster_port}")
        return mongo_client

    def _create_database(self) -> None:
        db = self._mongo_client[self._settings.db_name]
        if self._settings.read_only_user_name:
            self._run_operation_with_retry(
                self._create_user,
                db,
                self._settings.read_only_user_password_secret_name,
                self._settings.read_only_user_name
            )
        if self._settings.read_write_user_name:
            self._run_operation_with_retry(
                self._create_user,
                db,
                self._settings.read_write_user_password_secret_name,
                self._settings.read_write_user_name
            )
        self._run_operation_with_retry(self._create_shards, db, self._mongo_client)
        self._run_operation_with_retry(self._create_indexes, db)


    def _update_database(self) -> None:
        raise NotImplementedError("Update operation not implemented.")


    def _delete_database(self) -> None:
        raise NotImplementedError("Delete operation not implemented.")

    def _create_user(self, db: Database, secret_name: str, user_name: str) -> None:
        password = self.get_secret(secret_name)
        logger.info(f"Creating user: {user_name}")
        db.command({
            "createUser": user_name,
            "pwd": password,
            "roles": [
                {"role": BuiltInMongoDBRoles.READ.value, "db": db.name},
            ],
        })


    def _create_shards(self, db: Database, client: pymongo.MongoClient) -> None:
        client.admin.command('enableSharding', db.name)
        for col_name in self._config.collection_indexes:
            db.command({
                "shardCollection": f"{db.name}.{col_name}",
                "key": {"_id": "hashed"},
            })
            logger.info(f"Created shard for collection: {col_name}")


    def _create_indexes(self, db: Database) -> None:
        for col_name in self._config.collection_indexes:
            for doc_field_name in self._config.collection_indexes.get(col_name, []):
                logger.info(f"Creating index for doc field: {doc_field_name} in collection: {col_name}")
                db[col_name].create_index(doc_field_name)
