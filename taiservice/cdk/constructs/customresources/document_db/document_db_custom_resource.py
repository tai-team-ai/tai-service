"""Define the Lambda function for initializing the database."""
from typing import Any
from loguru import logger
import pymongo
from pymongo.database import Database
from pymongo.errors import OperationFailure
from settings import RuntimeDocumentDBSettings, MongoDBUser
# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_typing.events import CloudFormationCustomResourceEvent
except ImportError:
    from custom_resource_interface import CustomResourceInterface
    LambdaContext = CloudFormationCustomResourceEvent = Any


class DocumentDBCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: RuntimeDocumentDBSettings) -> None:
        super().__init__(event, context)
        secret = self.get_secret(settings.secret_name)
        self._admin_username = secret[settings.username_secret_field_name]
        self._admin_password = secret[settings.password_secret_field_name]
        self._settings = settings
        self._mongo_client = self._run_operation_with_retry(self._connect_to_database)

    def _connect_to_database(self) -> pymongo.MongoClient:
        logger.info("Creating MongoDB client")
        settings = self._settings
        uri = f"mongodb://{self._admin_username}:{self._admin_password}@{settings.cluster_host_name}:{settings.cluster_port}/?tls=true&retryWrites=false"
        logger.info(f"Connecting to cluster at {settings.cluster_host_name}:{settings.cluster_port}")
        mongo_client = pymongo.MongoClient(
            uri,
            serverSelectionTimeoutMS=settings.server_selection_timeout_MS,
        )
        logger.info(mongo_client.server_info())
        logger.info(f"Successfully connected to cluster at {settings.cluster_host_name}:{settings.cluster_port}")
        return mongo_client

    def _create_database(self) -> None:
        self._run_database_operation(self._create_user)

    def _update_database(self) -> None:
        self._run_database_operation(self._update_user)

    def _run_database_operation(self, user_operation: callable) -> None:
        db = self._mongo_client[self._settings.db_name]
        for user in self._settings.user_config:
            secret = self.get_secret(user.secret_name)
            username = secret[user.username_secret_field_name]
            password = secret[user.password_secret_field_name]
            self._run_operation_with_retry(user_operation, db, user, username, password)
        self._run_operation_with_retry(self._create_shards, db, self._mongo_client)
        self._run_operation_with_retry(self._create_collections, db)
        self._run_operation_with_retry(self._create_indexes, db)

    def _delete_database(self) -> None:
        # AWS will delete the database for us, so we don't need to do anything here.
        pass

    def _create_user(self, db: Database, user: MongoDBUser, username: str, password: str) -> None:
        logger.info(f"Creating user: {username}")
        db.command({
            "createUser": username,
            "pwd": password,
            "roles": [
                {"role": user.role, "db": db.name},
            ],
        })

    def _update_user(self, db: Database, user: MongoDBUser, username: str, password: str) -> None:
        logger.info(f"Updating user: {username}")
        db.command({
            "updateUser": username,
            "pwd": password,
            "roles": [
                {"role": user.role, "db": db.name},
            ],
        })

    def _create_collections(self, db: Database) -> None:
        for config in self._settings.collection_config:
            logger.info(f"Inserting dummy document into collection: {config.name}")
            db[config.name].insert_one({"_id": "dummy"})
            db[config.name].delete_one({"_id": "dummy"})
            logger.info(f"Successfully inserted & deleted dummy document into collection: {config.name}")

    def _create_shards(self, db: Database, client: pymongo.MongoClient) -> None:
        client.admin.command('enableSharding', db.name)
        for config in self._settings.collection_config:
            try:
                db.command({
                    "shardCollection": f"{db.name}.{config.name}",
                    "key": {"_id": "hashed"},
                })
                logger.info(f"Created shard for collection: {config.name}")
            except OperationFailure:
                logger.info(f"Shard for collection: {config.name} already exists")

    def _create_indexes(self, db: Database) -> None:
        for config in self._settings.collection_config:
            for doc_field_name in config.fields_to_index:
                logger.info(f"Creating index for doc field: {doc_field_name} in collection: {config.name}")
                db[config.name].create_index(doc_field_name)
