"""Define the lambda function for initializing the Pinecone database."""
import json
import traceback
from loguru import logger
from document_db_custom_resource import RuntimeDocumentDBSettings, DocumentDBCustomResource
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
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        settings = RuntimeDocumentDBSettings()
        custom_resource = DocumentDBCustomResource(event, context, settings)
        custom_resource.execute_crud_operation()
    except Exception:
        logger.exception("An exception occurred while running the custom resource.")
        logger.info(traceback.format_exc())
