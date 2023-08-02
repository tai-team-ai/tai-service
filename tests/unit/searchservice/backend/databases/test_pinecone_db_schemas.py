"""Define tests for the pinecone db schemas."""
import copy
import uuid
import pytest
from pydantic import ValidationError
from taiservice.searchservice.backend.databases.pinecone_db_schemas import (
    BasePydanticModel,
    PineconeDocument,
    PineconeDocuments,
    ChunkMetadata,
)
from taiservice.searchservice.backend.shared_schemas import Metadata
from .test_shared_schemas import EXAMPLE_METADATA, assert_schema1_inherits_from_schema2

def test_chunk_metadata_schema():
    """Ensure the schema doesn't change for ChunkMetadata."""
    assert_schema1_inherits_from_schema2(ChunkMetadata, Metadata)

def test_pinecone_document_schema():
    """Ensure the schema doesn't change for PineconeDocument."""
    assert_schema1_inherits_from_schema2(PineconeDocument, BasePydanticModel)

def test_pinecone_documents_schema():
    """Ensure the schema doesn't change for PineconeDocuments."""
    assert_schema1_inherits_from_schema2(PineconeDocuments, BasePydanticModel)

EXAMPLE_CHUNK_METADATA = {
    "class_id": "123e4567-e89b-12d3-a456-426614174000",
    "page_number": 1,
    "timestamp": "2021-01-01 00:00:00",
    "vector_id": "123e4567-e89b-12d3-a456-426614174000",
    "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
}
EXAMPLE_CHUNK_METADATA.update(EXAMPLE_METADATA)
EXAMPLE_PINECONE_DOCUMENT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "values": [1.0, 2.0, 3.0],
    "metadata": EXAMPLE_CHUNK_METADATA,
}

def test_chunk_metadata_model():
    """Define test for ChunkMetadata model."""
    metadata = ChunkMetadata(**EXAMPLE_CHUNK_METADATA)
    assert str(metadata.class_id) == EXAMPLE_CHUNK_METADATA["class_id"]

def test_pinecone_document_model():
    """Define test for PineconeDocument model."""
    doc = PineconeDocument(**EXAMPLE_PINECONE_DOCUMENT)
    assert str(doc.id) == EXAMPLE_PINECONE_DOCUMENT["id"]
    assert doc.values == EXAMPLE_PINECONE_DOCUMENT["values"]
    assert doc.metadata.dict(serialize_dates=True) == EXAMPLE_CHUNK_METADATA


EXAMPLE_PINECONE_DOCUMENTS = {
    "documents": [PineconeDocument.parse_obj(EXAMPLE_PINECONE_DOCUMENT)],
}
def test_pinecone_documents_model():
    """Define test for PineconeDocuments model."""
    docs = PineconeDocuments(**EXAMPLE_PINECONE_DOCUMENTS)
    assert str(docs.class_id) == EXAMPLE_CHUNK_METADATA["class_id"]


EXAMPLE_METADATA_2 = copy.deepcopy(EXAMPLE_METADATA)
EXAMPLE_METADATA_2["class_id"] = uuid.uuid4()
EXAMPLE_PINECONE_DOCUMENT_2 = copy.deepcopy(EXAMPLE_PINECONE_DOCUMENT)
EXAMPLE_PINECONE_DOCUMENT_2["metadata"] = EXAMPLE_METADATA_2
EXAMPLE_PINECONE_DOCUMENTS_WITH_DUPLICATES = {
    # "documents": [EXAMPLE_PINECONE_DOCUMENT, EXAMPLE_PINECONE_DOCUMENT_2],
    "documents": [
        PineconeDocument(**EXAMPLE_PINECONE_DOCUMENT),
        PineconeDocument(**EXAMPLE_PINECONE_DOCUMENT_2),
    ],
}
def test_different_class_ids_throws():
    """Ensure that different class ids throw an error."""
    with pytest.raises(ValidationError):
        PineconeDocuments(**EXAMPLE_PINECONE_DOCUMENTS_WITH_DUPLICATES)
