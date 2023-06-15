"""Define the Lambda function for initializing the database."""
from enum import Enum
import json
import requests
from loguru import logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent
import boto3
from botocore.config import Config as BotoConfig
import pymongo

DELAY_BEFORE_CONNECTION_ATTEMPT = 5
MAX_NUM_ATTEMPTS = 3
DELAY_BETWEEN_ATTEMPTS = 5
SERVER_SELECTION_TIMEOUT = 30

# TODO add document schema here to build indexes and shards

# TODO add collection to document mappin
SETTINGS = {}

class Status(Enum):
    """Define the status of the database initialization."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


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
    logger.info("Received event: %s", event)
    try:
        _execute_crud_operation(event)
        _send_cloud_formation_response(event, context, Status.SUCCESS)
    except Exception as e:
        logger.exception(e)
        _send_cloud_formation_response(event, context, Status.FAILED, reason=str(e))


def _execute_crud_operation(event: CloudFormationCustomResourceEvent) -> None:
    try:
        admin_credentials = _get_secret(SETTINGS["admin_credentials_secret_name"]) # TODO add secret name to settings
        user_name = admin_credentials[SETTINGS["user_name_key"]] # TODO add user name key to settings
        password = admin_credentials[SETTINGS["password_key"]] # TODO add password key to settings
    except Exception as e:
        logger.exception(e)
        raise ValueError("Failed to retrieve admin credentials from Secrets Manager") from e
    mongodb = _get_mongo_database(user_name, password)
    if event["RequestType"] == "Create":
        logger.info("Creating database")
        _create_database(mongodb)
    elif event["RequestType"] == "Update":
        logger.info("Updating database")
        _update_database(mongodb)
    elif event["RequestType"] == "Delete":
        logger.info("Deleting database")
        _delete_database(mongodb)
    else:
        logger.error("Invalid request type: %s", event["RequestType"])
        raise ValueError(f"Invalid request type: {event['RequestType']}")


def _get_mongo_database(user_name: str, password: str) -> pymongo.database.Database:
    logger.info("Creating MongoDB client")
    mongo_client = pymongo.MongoClient(
        f"mongodb://{user_name}:{password}@{SETTINGS['host']}:{SETTINGS['port']}/?tls=true&retryWrites=false",
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT,
    )
    logger.info(mongo_client.server_info())
    db = mongo_client[SETTINGS["database_name"]] # TODO add database name to settings
    logger.info(f"Succesfully connected to database: {SETTINGS['database_name']}") # TODO add database name to settings
    return db


def _send_cloud_formation_response(
    event: CloudFormationCustomResourceEvent,
    context: LambdaContext,
    response_status: Status,
    response_data: dict=None,
    reason: str=None
) -> None:
    response_body = {
        "Status": response_status,
        "Reason": reason or f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data,
    }
    logger.info("Response body: %s", response_body)
    requests.put(event["ResponseURL"], data=json.dumps(response_body), timeout=5)


def _get_secret(secret_name: str) -> dict:
    logger.info("Retrieving secret: %s", secret_name)
    session = boto3.session.Session()
    boto_config = BotoConfig(
        retries={
            "max_attempts": MAX_NUM_ATTEMPTS,
            "mode": "standard",
        }
    )
    client = session.client(
        service_name="secretsmanager",
        config=boto_config,
    )
    secret_value_response = client.get_secret_value(SecretId=secret_name)
    return json.loads(secret_value_response["SecretString"])


def _create_database(db: pymongo.database.Database) -> None:
    pass


def _update_database(db: pymongo.database.Database) -> None:
    pass


def _delete_database(db: pymongo.database.Database) -> None:
    pass
