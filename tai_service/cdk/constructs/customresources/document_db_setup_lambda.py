"""Define the Lambda function for initializing the database."""
from enum import Enum
import json
import time
import requests
from loguru import logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent
import boto3
from botocore.config import Config as BotoConfig
import pymongo
from pymongo.database import Database
from pydantic import BaseModel
from .custom_resource_interface import CustomResourceInterface, Status


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
    lambda_handler = DocumentDBSetupLambda(event, context)
    lambda_handler.execute_crud_operation()


class DocumentDBSetupLambda(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def execute_crud_operation(self) -> None:
        event = self._event
        try:
            admin_credentials = self.get_secret(SETTINGS["admin_credentials_secret_name"]) # TODO add secret name to settings
            user_name = admin_credentials[SETTINGS["user_name_key"]] # TODO add user name key to settings
            password = admin_credentials[SETTINGS["password_key"]] # TODO add password key to settings
        except Exception as e:
            logger.exception(e)
            raise ValueError("Failed to retrieve admin credentials from Secrets Manager") from e
        client = self._get_mongo_client(user_name, password)
        mongodb = client[SETTINGS["database_name"]] # TODO add database name to settings
        if event["RequestType"] == "Create":
            logger.info("Creating database")
            self._create_database(mongodb, client)
        elif event["RequestType"] == "Update":
            logger.info("Updating database")
            self._update_database(mongodb)
        elif event["RequestType"] == "Delete":
            logger.info("Deleting database")
            self._delete_database(mongodb)
        else:
            logger.error(f"Invalid request type: {event['RequestType']}")
            raise ValueError(f"Invalid request type: {event['RequestType']}")


    def _get_mongo_client(self, user_name: str, password: str) -> pymongo.MongoClient:
        logger.info("Creating MongoDB client")
        mongo_client = pymongo.MongoClient(
            f"mongodb://{user_name}:{password}@{SETTINGS['host']}:{SETTINGS['port']}/?tls=true&retryWrites=false",
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT,
        )
        logger.info(mongo_client.server_info())
        # logger.info(f"Succesfully connected to database: {SETTINGS['database_name']}") # TODO add database name to settings
        return mongo_client

    def _create_database(self, db: pymongo.database.Database, client: pymongo.MongoClient) -> None:
        self._run_operation_with_retry(self._create_user, db, SETTINGS["user_read_write_credentials_secret_name"]) # TODO add user credentials secret name to settings
        self._run_operation_with_retry(self._create_user, db, SETTINGS["user_read_credentials_secret_name"]) # TODO add admin credentials secret name to settings
        self._run_operation_with_retry(self._create_shards, db, client)
        self._run_operation_with_retry(self._create_indexes, db)


    def _update_database(self, db: Database) -> None:
        pass


    def _delete_database(self, db: Database) -> None:
        pass

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
