"""Define the Lambda function for initializing the database."""
from enum import Enum
import json
from loguru import logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent
import pymongo
from pymongo.database import Database
from pydantic import BaseModel
# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
except ImportError:
    from custom_resource_interface import CustomResourceInterface


SERVER_SELECTION_TIMEOUT = 30

# TODO add document schema here to build indexes and shards
DOCUMENT_MAPPING = {}

# TODO add collection to document mappin
SETTINGS = {}

class CollectionSettings(BaseModel):
    """Define the settings for the collections."""

    # TODO add collection settings here


class BuiltInMongoDBRoles(Enum):
    """Define the built-in MongoDB roles."""

    READ = "read"
    READ_WRITE = "readWrite"


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
    settings = {} # TODO add settings here
    custom_resource = DocumentDBCustomResource(event, context, settings)
    custom_resource.execute_crud_operation()


class DocumentDBCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: dict) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings["admin_credentials_secret_name"]) # TODO add secret name to settings
        self._settings = settings
        self._mongo_client = self._run_operation_with_retry(self._connect_to_database, password)
    
    def _connect_to_database(self, password: str) -> pymongo.MongoClient:
        logger.info("Creating MongoDB client")
        mongo_client = pymongo.MongoClient(
            f"mongodb://{self._settings['user_name']}:{password}@{self._settings['host']}:{self._settings['port']}/?tls=true&retryWrites=false",
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT,
        )
        logger.info(mongo_client.server_info())
        logger.info("Succesfully connected to cluster.")
        return mongo_client

    def _create_database(self) -> None:
        db = self._mongo_client[SETTINGS["database_name"]] # TODO add database name to settings
        self._run_operation_with_retry(self._create_user, db, self._settings["user_read_write_credentials_secret_name"]) # TODO add user credentials secret name to settings
        self._run_operation_with_retry(self._create_user, db, self._settings["user_read_credentials_secret_name"]) # TODO add admin credentials secret name to settings
        self._run_operation_with_retry(self._create_shards, db, self._mongo_client)
        self._run_operation_with_retry(self._create_indexes, db)


    def _update_database(self) -> None:
        raise NotImplementedError("Update operation not implemented.")


    def _delete_database(self) -> None:
        raise NotImplementedError("Delete operation not implemented.")

    def _create_user(self, db: Database, secret_name: str) -> None:
        use_credentials = self.get_secret(secret_name)
        user_name = SETTINGS["user_name_key"] # TODO add user name key to settings
        password = use_credentials[SETTINGS["password_key"]] # TODO add password key to settings
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
        for field_name in CollectionSettings.__fields__:
            col_name = getattr(CollectionSettings, field_name)
            db[col_name].create_index(field_name)
            db.command({
                "shardCollection": f"{db.name}.{col_name}",
                "key": {field_name: "hashed"},
            })
            logger.info(f"Created shard for collection: {col_name}")


    def _create_indexes(self, db: Database) -> None:
        for field_name in CollectionSettings.__fields__:
            col_name = getattr(CollectionSettings, field_name)
            documents = DOCUMENT_MAPPING.get(col_name, {})
            for doc_field_name in documents:
                logger.info(f"Creating index for doc field: {doc_field_name} in collection: {col_name}")
                db[col_name].create_index(doc_field_name)
