"""Define the shared schemas used by the backend."""
from typing import Optional
from uuid import UUID
from pydantic import Field, HttpUrl, validator
from ..shared_schemas import (
    ChunkMetadata,
    Metadata,
    BaseClassResourceDocument,
    StatefulClassResourceDocument,
    ClassResourceProcessingStatus,
)
from ..tai_search.data_ingestor_schema import IngestedDocument


class ClassResourceDocument(StatefulClassResourceDocument):
    """Define the document model of the class resource."""
    child_resource_ids: list[UUID] = Field(
        default_factory=list,
        description=("The IDs of the child resource. This is useful when the provided "
            "resource is a webpage and the user wants to crawl the website for resources. "
            "In this case, the child resource ID of all child resources that are scraped "
            "from the webpage."
        ),
    )
    parent_resource_ids: list[UUID] = Field(
        default_factory=list,
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

    @validator("child_resource_ids")
    def validate_class_resource_chunk_and_vector_ids(cls, ids: list[UUID], values: dict) -> list[UUID]:
        """Validate the class resource chunk ids."""
        completed_status = ClassResourceProcessingStatus.COMPLETED
        if values.get("status") == completed_status and not ids:
            raise ValueError("The class resource child ids must NOT " \
                f"be empty if the status is {completed_status}. Values you provided: {values}"
            )
        return ids

    @staticmethod
    def from_ingested_doc(
        ingested_doc: IngestedDocument,
        status: ClassResourceProcessingStatus = ClassResourceProcessingStatus.PENDING,
    ) -> "ClassResourceDocument":
        """Convert the ingested document to a database document."""
        metadata = ingested_doc.metadata
        doc = ClassResourceDocument(
            _id=ingested_doc.id,
            class_id=ingested_doc.class_id,
            full_resource_url=ingested_doc.full_resource_url,
            preview_image_url=ingested_doc.preview_image_url,
            data_pointer=ingested_doc.full_resource_url,
            status=status,
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
    resource_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the class resource that this chunk belongs to.",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="The metadata of the class resource chunk.",
    )
    raw_chunk_url: Optional[HttpUrl] = Field(
        default=None,
        description="""
            If the chunk hasn't been augmented this likely will point to the raw parent resource, if it has
            been augmented, this may point to things such as a highlighted version of the pdf or be a link to 
            a specific timestamp in a youtube video.
        """,
    )

    @staticmethod
    def _ensure_same_class_id(metadata_class_id: UUID, class_id: Optional[UUID]) -> None:
        """Ensure the same class id."""
        assert metadata_class_id == class_id, \
            "The class id of the metadata must be the same as the class id " \
            f"of the class resource. Id of the metadata: {metadata_class_id}, " \
            f"id of the class resource: {class_id}"

    @validator("metadata")
    def validate_metadata(cls, metadata: ChunkMetadata, values: dict) -> ChunkMetadata:
        """Ensure the same class id."""
        cls._ensure_same_class_id(metadata.class_id, values.get("class_id"))
        metadata.chunk_id = values.get("id")
        return metadata
