"""Define the Lambda function for initializing the database."""
from enum import Enum
import json
from loguru import logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent
import pymongo
from pymongo.database import Database
from pydantic import BaseSettings, Field
# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
except ImportError:
    from custom_resource_interface import CustomResourceInterface


# TODO add document schema here to build indexes and shards
DOCUMENT_MAPPING = {}

class BuiltInMongoDBRoles(Enum):
    """Define the built-in MongoDB roles."""

    READ = "read"
    READ_WRITE = "readWrite"


class BaseDocumentDBSettings(BaseSettings):
    """Define the base settings for the document database."""

    cluster_host_name: str = Field(
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


class AdminDocumentDBSettings(BaseDocumentDBSettings):
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
    collection_indexes: dict[str, list[str]] = Field(
        ...,
        env="COLLECTION_INDEXES",
    )


def lambda_handler(event: CloudFormationCustomResourceEvent, context: LambdaContext) -> None:
    """
    Run the database initialization.
    
    This function is invoked by the CloudFormation custom resource. It is responsible for
    initializing the database by retrieving admin credentials from Secrets Manager and
    creating shards, collections, and indexes for the database.

    Currently, only create operations are supported, but this function could be extended
    to include all CRUD operations.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    settings = AdminDocumentDBSettings()
    custom_resource = DocumentDBCustomResource(event, context, settings)
    custom_resource.execute_crud_operation()


class DocumentDBCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: AdminDocumentDBSettings) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings.admin_user_password_secret_name)
        self._settings = settings
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
        self._run_operation_with_retry(
            self._create_user,
            db,
            self._settings.read_only_user_password_secret_name,
            self._settings.read_only_user_name
        )
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
        for col_name in self._settings.collection_names:
            db.command({
                "shardCollection": f"{db.name}.{col_name}",
                "key": {"_id": "hashed"},
            })
            logger.info(f"Created shard for collection: {col_name}")


    def _create_indexes(self, db: Database) -> None:
        for col_name in self._settings.collection_names:
            for doc_field_name in self._settings.collection_indexes[col_name]:
                logger.info(f"Creating index for doc field: {doc_field_name} in collection: {col_name}")
                db[col_name].create_index(doc_field_name)
