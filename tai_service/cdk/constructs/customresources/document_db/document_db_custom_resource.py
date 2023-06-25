"""Define the Lambda function for initializing the database."""
from typing import Any
from loguru import logger
import pymongo
from pymongo.database import Database
from .settings import RuntimeDocumentDBSettings, MongoDBUser
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
        # password = self.get_secret(settings.admin_user_password_secret_name)
        # self._settings = settings
        # self._mongo_client = self._run_operation_with_retry(self._connect_to_database, password)

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
