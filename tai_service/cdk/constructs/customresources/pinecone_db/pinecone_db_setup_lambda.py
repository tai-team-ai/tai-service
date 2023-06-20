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
    pod_instance_type: Optional[PodType] = Field(
        default=PodType.S1,
        description="Type of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    pod_size: Optional[PodSize] = Field(
        default=PodSize.X1,
        description="Size of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    pod_type: str = Field(
        default="",
        description="Used internally to create a fully qualified pod type (Example: s1.x1)",
    )
    metadata_config: Optional[MetaDataConfig] = Field(
        default=None,
        description="Metadata configuration for the index.",
    )
    source_collection: Optional[str] = Field(
        default=None,
        description="Name of the source collection to use for the index.",
    )

    @validator("pod_type", always=True)
    def validate_pod_type(cls, pod_type: str, values: Dict[str, Any]) -> str:
        """Validate the pod type."""
        if pod_type:
            logger.warning("Pod type should not be set manually. Overwriting value.")
        pod_instance_type = values.get("pod_instance_type")
        pod_size = values.get("pod_size")
        if pod_instance_type and pod_size:
            return f"{pod_instance_type.value}.{pod_size.value}"
        raise ValueError("Pod instance type and pod size must be set.")


class PineconeDBSettings(BasePineconeDBSettings):
    """Define the settings for the PineconeDBSetupLambda."""

    indexes: List[PineconeIndexConfig] = Field(
        ...,
        max_items=2,
        description="Config for the Pinecone indexes.",
    )

    @validator("indexes")
    def ensure_no_duplicate_indexes(cls, indexes: List[PineconeIndexConfig]) -> List[PineconeIndexConfig]:
        """Ensure that there are no duplicate indexes."""
        index_names = [index.name for index in indexes]
        if len(index_names) != len(set(index_names)):
            raise ValueError("Index names must be unique.")
        return indexes


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
        pinecone_options = index_settings.dict(
            exclude_none=True,
            exclude={"pod_size", "pod_instance_type"},
        )
        self._run_operation_with_retry(
            pinecone.create_index,
            **pinecone_options,
        )

    def _update_database(self) -> None:
        current_indexes = set(pinecone.list_indexes())
        new_indexes = set(index.name for index in self._settings.indexes)
        for index_name in current_indexes - new_indexes:
            self._delete_index(index_name)
        for index_config in self._settings.indexes:
            if index_config.name in current_indexes:
                self._update_index(index_config)
            else:
                self._create_index(index_config)

    def _update_index(self, index_settings: PineconeIndexConfig) -> None:
        self._validate_update_operation(index_settings)
        self._run_operation_with_retry(
            pinecone.configure_index,
            index_settings.name,
            index_settings.replicas,
            index_settings.pod_type,
        )

    def _validate_update_operation(self, index_settings: PineconeIndexConfig) -> None:
        pod_type = pinecone.describe_index(index_settings.name).pod_type
        current_pod_size = self._get_pod_size(pod_type)
        new_pod_size = self._get_pod_size(index_settings.pod_type)
        assert new_pod_size >= current_pod_size, f"Cannot downgrade pod size. Current pod size: {current_pod_size}, new pod size: {new_pod_size}"
        current_pod_type =  self._get_pod_type(pod_type)
        new_pod_type = self._get_pod_type(index_settings.pod_type)
        assert current_pod_type == new_pod_type, f"Cannot change pod type. Current pod type: {current_pod_type}, new pod type: {new_pod_type}"

    def _get_pod_type(self, pod_type: str) -> str:
        """Pod type is in the format s1.x1, so we need to split and get the first prefix (Example: s1)."""
        return pod_type.split(".")[0]

    def _get_pod_size(self, pod_type: str) -> int:
        """Pod type is in the format s1.x1, so we need to split and get the number."""
        return int(pod_type.split(".")[1][1:])

    def _delete_database(self) -> None:
        indexes = pinecone.list_indexes()
        for index in indexes:
            self._delete_index(index)

    def _delete_index(self, index: str) -> None:
        self._validate_can_delete_index(index)
        self._run_operation_with_retry(
            pinecone.delete_index,
            index,
        )

    def _validate_can_delete_index(self, index: str) -> None:
        """Validate that the index can be deleted."""
        try:
            index: pinecone.Index = pinecone.Index(index)
            stats = index.describe_index_stats()
        except Exception as e: # pylint: disable=broad-except
            logger.warning(f"Failed to get index stats for index {index}. Error: {e}")
            return
        assert stats["total_vector_count"] == 0, f"Cannot delete index {index} because it is not empty."
