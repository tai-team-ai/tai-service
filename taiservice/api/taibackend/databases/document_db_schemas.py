"""Define the shared schemas used by the backend."""
from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import Field, root_validator, validator
# first imports are for local development, second imports are for deployment
try:
    from ...taibackend.databases.shared_schemas import (
        ChunkMetadata,
        Metadata,
        BasePydanticModel,
    )
except ImportError:
    from taibackend.databases.shared_schemas import (
        ChunkMetadata,
        Metadata,
        BasePydanticModel,
    )

class ClassResourceProcessingStatus(str, Enum):
    """Define the document status."""

    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    COMPLETED = "completed"


class BaseClassResourceDocument(BasePydanticModel):
    """Define the base model of the class resource."""

    id: UUID = Field(
        ...,
        description="The ID of the class resource.",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    full_resource_url: str = Field(
        ...,
        description="The URL of the class resource.",
    )
    metadata: Metadata = Field(
        ...,
        description="The metadata of the class resource.",
    )
    create_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp when the class resource was created.",
    )
    modified_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp when the class resource was last modified.",
    )

    @validator("modified_timestamp", pre=True)
    def set_modified_timestamp(cls, _: datetime) -> datetime:
        """Set the modified timestamp."""
        return datetime.utcnow()


class ClassResourceDocument(BaseClassResourceDocument):
    """Define the document model of the class resource."""

    status: ClassResourceProcessingStatus = Field(
        ...,
        description=f"The processing status of the class resource. Valid values are: {', '.join([status.value for status in ClassResourceProcessingStatus])}",
    )
    class_resource_chunk_ids: list[UUID] = Field(
        default_factory=list,
        description="The IDs of the class resource chunks.",
    )

    @validator("class_resource_chunk_ids")
    def validate_class_resource_chunk_and_vector_ids(cls, ids: list[UUID], values: dict) -> list[UUID]:
        """Validate the class resource chunk ids."""
        completed_status = ClassResourceProcessingStatus.COMPLETED
        if values.get("status") == completed_status and not ids:
            raise ValueError(f"Both the class resource chunk ids and chunk vector "\
                f"ids must not be empty if the status is {completed_status}. Values you provided: {values}"
            )
        return ids


class ClassResourceChunkDocument(BaseClassResourceDocument):
    """Define the snippet model of the class resource."""

    chunk: str = Field(
        ...,
        description="The text chunk of the class resource.",
    )
    vector_id: UUID = Field(
        default_factory=list,
        description="The ID of the class resource chunk vector.",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="The metadata of the class resource chunk.",
    )

    @root_validator(pre=True)
    def add_class_id_to_metadata(cls, values: dict) -> dict:
        """Add the class id to the metadata."""
        values['metadata']['class_id'] = values['class_id']
        return values
