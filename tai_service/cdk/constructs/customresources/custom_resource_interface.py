"""Define custom resource class for constructs."""

from abc import ABC, abstractmethod
import json
from enum import Enum
from typing import Optional
from loguru import logger
import requests
import boto3
from botocore.config import Config as BotoConfig
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent


class Status(Enum):
    """Define the status of the database initialization."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class CustomResourceInterface(ABC):
    """Define an interface for custom resources."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext) -> None:
        super().__init__()
        self._event = event
        self._context = context

    @abstractmethod
    def execute_crud_operation(self) -> None:
        """Execute the CRUD operation."""

    def _send_cloud_formation_response(
        self,
        status: Status,
        reason: Optional[str] = None,
        physical_resource_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> None:
        """Send a response to CloudFormation."""
        response = {
            "Status": status.value,
            "Reason": reason,
            "PhysicalResourceId": physical_resource_id,
            "StackId": self._event["StackId"],
            "RequestId": self._event["RequestId"],
            "LogicalResourceId": self._event["LogicalResourceId"],
            "Data": data,
        }
        logger.info(f"Sending response: {json.dumps(response)}")
        requests.put(self._event["ResponseURL"], data=json.dumps(response), timeout=15)

    def _get_secret(secret_name: str) -> dict:
        logger.info(f"Retrieving secret: {secret_name}")
        session = boto3.session.Session()
        boto_config = BotoConfig(
            retries={
                "max_attempts": 3,
                "mode": "standard",
            }
        )
        client = session.client(
            service_name="secretsmanager",
            config=boto_config,
        )
        secret_value_response = client.get_secret_value(SecretId=secret_name)
        return json.loads(secret_value_response["SecretString"])
