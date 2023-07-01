"""Define the shared schemas used by the backend."""
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, root_validator, validator


class ClassResourceProcessingStatus(str, Enum):
    """Define the document status."""

    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    COMPLETED = "completed"

class ClassResourceType(str, Enum):
    """Define the built-in MongoDB roles."""

    # VIDEO = "video"
    # TEXT = "text"
    # IMAGE = "image"
    # AUDIO = "audio"
    PDF = "pdf"

class Metadata(BaseModel):
    """Define the metadata of the class resource."""

    title: str = Field(
        ...,
        description="The title of the class resource. This can be the file name or url if no title is provided.",
    )
    description: str = Field(
        ...,
        description="The description of the class resource.",
    )
    tags: list = Field(
        default_factory=list,
        description="The tags of the class resource.",
    )
    resource_type: str = Field(
        ...,
        description="The type of the class resource.",
    )
    total_page_count: Optional[int] = Field(
        default=None,
        description="The page count of the class resource.",
    )

class BaseClassResourceDocument(BaseModel):
    """Define the base model of the class resource."""

    id: UUID = Field(
        ...,
        description="The ID of the class resource.",
    )
    class_id: str = Field(
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
    def validate_class_resource_chunk_ids(cls, ids: list[UUID], values: dict) -> list[UUID]:
        """Validate the class resource chunk ids."""
        completed_status = ClassResourceProcessingStatus.COMPLETED
        if values.get("status") == completed_status:
            if not ids:
                raise ValueError(f"The class resource chunk ids must NOT be empty if the status is {completed_status}.")
        else:
            if ids:
                raise ValueError(f"The class resource chunk ids must be empty if the status is NOT {completed_status}.")
        return ids


class ChunkMetadata(Metadata):
    """Define the metadata of the class resource chunk."""

    class_id: str = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="The page number of the class resource.",
    )
    time_stamp: Optional[int] = Field(
        default=None,
        description="The time stamp of the class resource.",
    )


class ClassResourceChunkDocument(BaseClassResourceDocument):
    """Define the snippet model of the class resource."""

    chunk: str = Field(
        ...,
        description="The chunk of the class resource.",
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
