"""Define schemas for Pinecone database models."""
from typing import Dict, Optional
from uuid import UUID
from pydantic import Field, root_validator, Extra
# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )
except ImportError:
    from taiservice.api.taibackend.shared_schemas import (
        ChunkMetadata,
        BasePydanticModel,
    )

class SparseVector(BasePydanticModel):
    """Define the sparse vector model of the class resource."""

    indices: list[int] = Field(
        ...,
        description="The indices of the sparse vector of the class resource.",
    )
    values: list[float] = Field(
        ...,
        description="The values of the sparse vector of the class resource.",
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
    sparse_values: Optional[SparseVector] = Field(
        description="The sparse vector of the class resource.",
        alias="sparseValues",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="The metadata of the class resource.",
    )
    score: Optional[float] = Field(
        default=None,
        description="The similarity score of the vector if returned in response to a query.",
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
        validate_assignment = True
        extra = Extra.ignore

    @root_validator(pre=True)
    def ensure_all_have_same_class_id_and_set_namespace(cls, values: Dict) -> Dict:
        """Ensure that all documents have the same class id."""
        class_id = set()
        document: PineconeDocument
        for document in values["documents"]:
            class_id.add(document.metadata.class_id)
        if len(class_id) != 1:
            raise ValueError("")
        values.update({"class_id": class_id.pop()})
        return values
