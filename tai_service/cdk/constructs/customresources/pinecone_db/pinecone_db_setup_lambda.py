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

    S1 = "s1"
    P1 = "p1"
    P2 = "p2"

class PodSize(str, Enum):
    """Define the pod sizes."""

    X1 = "x1"
    X2 = "x2"
    X4 = "x4"
    X8 = "x8"


class DistanceMetric(str, Enum):
    """Define the distance metrics."""

    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    DOT_PRODUCT = "dotproduct"


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
        PodType.S1,
        description="Type of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    pod_size: Optional[PodSize] = Field(
        PodSize.X1,
        description="Size of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    metadata_config: Optional[MetaDataConfig] = Field(
        default=None,
        description="Metadata configuration for the index.",
    )
    source_collection: Optional[str] = Field(
        default=None,
        description="Name of the source collection to use for the index.",
    )

    @property
    def pod_type(self) -> str:
        """Return the pod type as a string."""
        return self.pod_type.value + "." + self.pod_size.value


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
            **index_settings.dict(exclude_none=True),
        )

    def _update_database(self) -> None:
        # check if the indexes exist
        # if it doesn't exist, create it
        # if it does, we can only update the pod type and replicas
        indexes = set(pinecone.list_indexes())
        for index_config in self._settings.indexes:
            if index_config.name in indexes:
                self._update_index(index_config)
            else:
                self._create_index(index_config)

    def _update_index(self, index_settings: PineconeIndexConfig) -> None:
        pod_type = pinecone.describe_index(index_settings.name).pod_type
        current_pod_size = self._get_pod_size(pod_type)
        new_pod_size = self._get_pod_size(index_settings.pod_type)
        assert new_pod_size >= current_pod_size, f"Cannot downgrade pod size. Current pod size: {current_pod_size}, new pod size: {new_pod_size}"
        self._run_operation_with_retry(
            pinecone.configure_index,
            index_settings.name,
            index_settings.replicas,
            index_settings.pod_type,
        )

    def _get_pod_size(self, pod_type: str) -> int:
        """Pod type is in the format s1.x1, so we need to split and get the number."""
        return int(pod_type.split(".")[1][1:])

    def _delete_database(self) -> None:
        indexes = pinecone.list_indexes()
        self._delete_indexes(indexes)

    def _delete_indexes(self, indexes: List[str]) -> None:
        for index in indexes:
            self._run_operation_with_retry(
                pinecone.delete_index,
                index,
            )
