"""Defines the PineconeDBSetupLambda class and handler."""
from enum import Enum
import json
from typing import Any, Dict, List, Optional, TypedDict
from loguru import logger
from pydantic import BaseModel, Field, validator
import pinecone

# first imports are for local development, second imports are for deployment
try:
    from ..custom_resource_interface import CustomResourceInterface
    from tai_service.schemas import BasePineconeDBSettings
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_typing.events import CloudFormationCustomResourceEvent
except ImportError:
    from custom_resource_interface import CustomResourceInterface
    from schemas import BasePineconeDBSettings
    LambdaContext = CloudFormationCustomResourceEvent = Any


class MetaDataConfig(TypedDict):
    """Define the metadata configuration for the Pinecone index."""

    field_names: List[str]


class PodType(str, Enum):
    """Define the pod types."""

    S1x1 = "s1.x1"
    # S1x2 = "s1.x2"
    # S1x4 = "s1.x4"
    # S1x8 = "s1.x8"
    P1x1 = "p1.x1"
    # P1x2 = "p1.x2"
    # P1x4 = "p1.x4"
    # P1x8 = "p1.x8"
    P2x1 = "p2.x1"
    # P2x2 = "p2.x2"
    # P2x4 = "p2.x4"
    # P2x8 = "p2.x8"


class DistanceMetric(str, Enum):
    """Define the distance metrics."""

    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"


class PineconeIndexConfig(BaseModel):
    """Define the settings for the Pinecone index."""

    name: str = Field(
        ...,
        max_length=45,
        description="Name of the index.",
    )
    dimension: int = Field(
        ...,
        description="Dimension of vectors stored in the index.",
    )
    metric: Optional[DistanceMetric] = Field(
        DistanceMetric.DOT_PRODUCT,
        description="Distance metric used to compute the distance between vectors.",
    )
    pods: Optional[int] = Field(
        default=1,
        le=2,
        ge=1,
        description="Number of pods to use for the index.",
    )
    replicas: Optional[int] = Field(
        default=1,
        le=1,
        ge=1,
        description="Number of replicas to use for the index.",
    )
    pod_type: Optional[PodType] = Field(
        PodType.S1x1,
        description="Type of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    metadata_config: Optional[MetaDataConfig] = Field(
        default=None,
        description="Metadata configuration for the index.",
    )
    source_collection: Optional[str] = Field(
        default=None,
        description="Name of the source collection to use for the index.",
    )


class PineconeDBSettings(BasePineconeDBSettings):
    """Define the settings for the PineconeDBSetupLambda."""

    indexes: List[PineconeIndexConfig] = Field(
        ...,
        max_items=2,
        description="Config for the Pinecone indexes.",
    )


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
    settings = PineconeDBSettings()
    custom_resource = PineconeDBSetupCustomResource(event, context, settings)
    custom_resource.execute_crud_operation()


class PineconeDBSetupCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(self, event: CloudFormationCustomResourceEvent, context: LambdaContext, settings: PineconeDBSettings) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings.api_key_secret_name)
        self._settings = settings
        pinecone.init(
            api_key=password,
            environment=settings.environment,
        )

    def _create_database(self) -> None:
        for index_config in self._settings.indexes:
            self._create_index(index_config)

    def _create_index(self, index_settings: PineconeIndexConfig) -> None:
        self._run_operation_with_retry(
            pinecone.create_index,
            **index_settings.dict(),
        )

    def _update_database(self) -> None:
        raise NotImplementedError("Update operation not implemented.")


    def _delete_database(self) -> None:
        raise NotImplementedError("Delete operation not implemented.")
