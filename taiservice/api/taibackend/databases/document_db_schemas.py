"""Define the shared schemas used by the backend."""
from datetime import datetime
from enum import Enum
from typing import Optional
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
    child_resource_id: Optional[UUID] = Field(
        default=None,
        description=("The ID of the child resource. This is useful when the provided "
            "resource is a webpage and the user wants to crawl the website for resources. "
            "In this case, the child resource ID of all child resources that are scraped "
            "from the webpage."
        ),
    )
    parent_resource_id: Optional[UUID] = Field(
        default=None,
        description=("The ID of the parent resource. This field must be populated if the "
            "resource is a child of another resource. For example, if the resource is a "
            "webpage, then the parent resource ID is the ID of the webpage that contains "
            "the parent resource."
        ),
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

    @validator("metadata")
    def ensure_same_class_id(cls, metadata: ChunkMetadata, values: dict) -> ChunkMetadata:
        """Ensure the same class id."""
        assert metadata.class_id == values.get("class_id"), \
            "The class id of the metadata must be the same as the class id " \
            f"of the class resource. Id of the metadata: {metadata.class_id}, " \
            f"id of the class resource: {values.get('class_id')}"
        return metadata
