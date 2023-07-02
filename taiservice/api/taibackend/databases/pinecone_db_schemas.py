"""Define schemas for Pinecone database models."""
from typing import Dict, Optional
from uuid import UUID
from pydantic import Field, root_validator, Extra
# first imports are for local development, second imports are for deployment
try:
    from ...taibackend.databases.shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )
except ImportError:
    from taibackend.databases.shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )

# This conforms to the pinecone document schema for a vector
# https://docs.pinecone.io/docs/python-client#indexupsert
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
    sparse_vector: Optional[dict[int, float]] = Field(
        description="The sparse vector of the class resource.",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="The metadata of the class resource.",
    )

# this is modeled to match the query response from pinecone
# https://docs.pinecone.io/docs/python-client#indexquery
class PineconeDocuments(BasePydanticModel):
    """Define the documents model of the class resource."""

    class_id: UUID = Field(
        ...,
        description="The namespace of the class resource.",
        alias="namespace",
    )
    documents: list[PineconeDocument] = Field(
        ...,
        description="The documents of the class resource.",
        alias="matches",
    )

    class Config:
        """Define the config for the pinecone documents model."""

        allow_population_by_field_name = True
        extra = Extra.ignore

    @root_validator(pre=True)
    def ensure_all_have_same_class_id_and_set_namespace(cls, values: Dict) -> Dict:
        """Ensure that all documents have the same class id."""
        class_id = set()
        for document in values["documents"]:
            class_id.add(document["metadata"]["class_id"])
        if len(class_id) != 1:
            raise ValueError("All documents must have the same class id.")
        values.update({"class_id": class_id.pop()})
        return values
