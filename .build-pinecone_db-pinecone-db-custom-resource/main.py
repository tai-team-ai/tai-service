"""Define the lambda function for initializing the Pinecone database."""
import json
from loguru import logger
from pinecone_db_custom_resource import (
    PineconeDBSetupCustomResource,
    PineconeDBSettings,
)
# first imports are for local development, second imports are for deployment
try:
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_typing.events import CloudFormationCustomResourceEvent
except ImportError:
    from typing import Any
    LambdaContext = CloudFormationCustomResourceEvent = Any


def lambda_handler(event: CloudFormationCustomResourceEvent, context: LambdaContext) -> None:
    """
    Run the database operation.

    This function is invoked by the CloudFormation custom resource. It is responsible for
    running CRUD operations on the database by retrieving admin credentials from Secrets Manager and
    creating indexes for the database.

    Currently, only create operations are supported, but this function could be extended
    to include all CRUD operations.
    """

    logger.info(f"Received event: {json.dumps(event)}")
    config = PineconeDBSettings()
    # custom_resource = PineconeDBSetupCustomResource(event, context, config)
    # custom_resource.execute_crud_operation()
