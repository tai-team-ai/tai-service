"""Defines the PineconeDBSetupLambda class and handler."""
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_typing.events import CloudFormationCustomResourceEvent
from loguru import logger
import pinecone

# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
except ImportError:
    from custom_resource_interface import CustomResourceInterface


class MetaDataConfig(TypedDict):
    """Define the metadata configuration for the Pinecone index."""

    indexed: List[str]

class PodType(Enum):
    """Define the pod types."""

    S1x1 = "s1.x1"
    S1x2 = "s1.x2"
    S1x4 = "s1.x4"
    S1x8 = "s1.x8"
    P1x1 = "p1.x1"
    P1x2 = "p1.x2"
    P1x4 = "p1.x4"
    P1x8 = "p1.x8"
    P2x1 = "p2.x1"
    P2x2 = "p2.x2"
    P2x4 = "p2.x4"
    P2x8 = "p2.x8"


class DistanceMetric(Enum):
    """Define the distance metrics."""

    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"


class PineconeIndexSettings(TypedDict):
    """Define the settings for the Pinecone index."""

    name: str
    dimension: int
    metric: Optional[str]
    pods: Optional[int]
    replicas: Optional[int]
    pod_type: Optional[str]
    metadata_config: Optional[MetaDataConfig]
    source_collection: Optional[str]


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
    custom_resource = PineconeDBSetupCustomResource(event, context, settings)
    custom_resource.execute_crud_operation()


class PineconeDBSetupCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: dict) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings["admin_credentials_secret_name"]) # TODO add secret name to settings
        self._settings = settings
        pinecone.init(
            api_key=password,
            environment=self._settings["environment"],
            project_name=self._settings["project_name"],
        )

    def _create_database(self) -> None:
        config = PineconeIndexSettings(
            name=self._settings["index_name"],
            dimension=self._settings["dimension"],
            metric=self._settings["metric"],
            pods=self._settings["pods"],
            replicas=self._settings["replicas"],
            pod_type=self._settings["pod_type"],
            metadata_config=self._settings["metadata_config"],
            source_collection=self._settings["source_collection"],
        )
        self._run_operation_with_retry(
            pinecone.create_index,
            kwargs=config,
        )

    def _update_database(self) -> None:
        raise NotImplementedError("Update operation not implemented.")


    def _delete_database(self) -> None:
        raise NotImplementedError("Delete operation not implemented.")
