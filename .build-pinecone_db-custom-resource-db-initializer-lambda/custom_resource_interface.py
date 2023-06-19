"""Define custom resource class for constructs."""

from abc import ABC, abstractmethod
import json
from enum import Enum
import time
from typing import Optional
import traceback
from loguru import logger
import requests
import boto3
from botocore.config import Config as BotoConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent


DELAY_BEFORE_CONNECTION_ATTEMPT = 5
MAX_NUM_ATTEMPTS = 3
DELAY_BETWEEN_ATTEMPTS = 5


class CRUDOperation(Enum):
    """Define the CRUD operations."""

    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"


class CustomResourceInterface(ABC):
    """Define an interface for custom resources."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext) -> None:
        super().__init__()
        self._event = event
        self._context = context

    def execute_crud_operation(self) -> None:
        """Execute the CRUD operation."""
        request_type = self._event["RequestType"]
        if request_type == CRUDOperation.CREATE.value:
            logger.info("Creating database")
            self._create_database()
        elif request_type == CRUDOperation.UPDATE.value:
            logger.info("Updating database")
            self._update_database()
        elif request_type == CRUDOperation.DELETE.value:
            logger.info("Deleting database")
            self._delete_database()
        else:
            raise ValueError(f"Invalid request type: {request_type}")

    @staticmethod
    def get_secret(secret_name: str) -> dict:
        """Retrieve a secret from AWS Secrets Manager."""
        logger.info(f"Retrieving secret: {secret_name}")
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

    @abstractmethod
    def _create_database(self) -> None:
        """Create the database."""

    @abstractmethod
    def _update_database(self) -> None:
        """Update the database."""

    @abstractmethod
    def _delete_database(self) -> None:
        """Delete the database."""

    def _run_operation_with_retry(self, operation: callable, *args, **kwargs) -> None:
        for attempt in range(MAX_NUM_ATTEMPTS):
            try:
                return operation(*args, **kwargs)
            except Exception as e: # pylint: disable=broad-except
                logger.exception(e)
                logger.info(f"Attempt {attempt + 1} of {MAX_NUM_ATTEMPTS} failed. Retrying in {DELAY_BETWEEN_ATTEMPTS} seconds...")
                time.sleep(DELAY_BETWEEN_ATTEMPTS)
        logger.error(f"Failed to run operation: {operation.__name__}")
        raise e
