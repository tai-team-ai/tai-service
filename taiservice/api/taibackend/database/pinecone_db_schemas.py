"""Define schemas for Pinecone database models."""
from uuid import UUID
from pydantic import Field
# first imports for dev, second for prod
try:
    from taiservice.api.taibackend.database.shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )
except ImportError:
    from taibackend.database.shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )

class PineconeDocument(BasePydanticModel):
    """Define the document model of the class resource."""

    id: UUID = Field(
        ...,
        description="The ID of the class resource.",
    )
    values: list[float] = Field(
        ...,
        description="The dense vector of the class resource.",
    )
    sparse_vector: dict[int, float] = Field(
        ...,
        description="The sparse vector of the class resource.",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="The metadata of the class resource.",
    )
