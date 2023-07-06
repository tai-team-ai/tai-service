"""Define the shared schemas used by the backend."""
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import Field, validator
# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import (
        ChunkMetadata,
        Metadata,
        BaseClassResourceDocument,
        StatefulClassResourceDocument,
    )
    from ..indexer.data_ingestor_schema import IngestedDocument
except ImportError:
    from taiservice.api.taibackend.shared_schemas import (
        ChunkMetadata,
        Metadata,
        BaseClassResourceDocument,
        StatefulClassResourceDocument,
    )
    from taibackend.indexer.data_ingestor_schema import IngestedDocument


class ClassResourceProcessingStatus(str, Enum):
    """Define the document status."""
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    DELETING = "deleting"
    COMPLETED = "completed"


class ClassResourceDocument(StatefulClassResourceDocument):
    """Define the document model of the class resource."""
    status: ClassResourceProcessingStatus = Field(
        ...,
        description=f"The processing status of the class resource. Valid values are: {', '.join([status.value for status in ClassResourceProcessingStatus])}",
    )
    child_resource_ids: Optional[list[UUID]] = Field(
        default=None,
        description=("The IDs of the child resource. This is useful when the provided "
            "resource is a webpage and the user wants to crawl the website for resources. "
            "In this case, the child resource ID of all child resources that are scraped "
            "from the webpage."
        ),
    )
    parent_resource_ids: Optional[list[UUID]] = Field(
        default=None,
        description=("The IDs of the parent resource. This field must be populated if the "
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
            raise ValueError("The class resource chunk ids must NOT " \
                f"be empty if the status is {completed_status}. Values you provided: {values}"
            )
        return ids

    @staticmethod
    def from_ingested_doc(ingested_doc: IngestedDocument) -> 'ClassResourceDocument':
        """Convert the ingested document to a database document."""
        metadata = ingested_doc.metadata
        doc = ClassResourceDocument(
            id=ingested_doc.id,
            class_id=ingested_doc.class_id,
            full_resource_url=ingested_doc.full_resource_url,
            preview_image_url=ingested_doc.preview_image_url,
            status=ClassResourceProcessingStatus.PENDING,
            hashed_document_contents=ingested_doc.hashed_document_contents,
            metadata=Metadata(
                title=metadata.title,
                description=metadata.description,
                tags=metadata.tags,
                resource_type=metadata.resource_type,
            )
        )
        return doc


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
