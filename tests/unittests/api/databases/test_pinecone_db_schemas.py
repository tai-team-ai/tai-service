"""Define tests for the pinecone db schemas."""
import copy
import uuid
import pytest
from taiservice.api.taibackend.databases.pinecone_db_schemas import (
    BasePydanticModel,
    PineconeDocument,
    PineconeDocuments,
    ChunkMetadata,
)
from taiservice.api.taibackend.databases.shared_schemas import Metadata
from .test_shared_schemas import EXAMPLE_METADATA, assert_schema2_inherits_from_schema1

def test_chunk_metadata_schema():
    """Ensure the schema doesn't change for ChunkMetadata."""
    assert_schema2_inherits_from_schema1(ChunkMetadata, Metadata)

def test_pinecone_document_schema():
    """Ensure the schema doesn't change for PineconeDocument."""
    assert_schema2_inherits_from_schema1(PineconeDocument, BasePydanticModel)

def test_pinecone_documents_schema():
    """Ensure the schema doesn't change for PineconeDocuments."""
    assert_schema2_inherits_from_schema1(PineconeDocuments, BasePydanticModel)

EXAMPLE_CHUNK_METADATA = {
    "class_id": "123e4567-e89b-12d3-a456-426614174000",
    "page_number": 1,
}
EXAMPLE_CHUNK_METADATA.update(EXAMPLE_METADATA)
EXAMPLE_PINECONE_DOCUMENT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "values": [1.0, 2.0, 3.0],
    "metadata": EXAMPLE_CHUNK_METADATA,
}

def test_pinecone_document_model():
    """Define test for PineconeDocument model."""
    doc = PineconeDocument(**EXAMPLE_PINECONE_DOCUMENT)
    assert str(doc.id) == EXAMPLE_PINECONE_DOCUMENT["id"]
    assert doc.values == EXAMPLE_PINECONE_DOCUMENT["values"]

EXAMPLE_PINECONE_DOCUMENTS = {
    "documents": [EXAMPLE_PINECONE_DOCUMENT],
}

def test_pinecone_documents_model():
    """Define test for PineconeDocuments model."""
    docs = PineconeDocuments(**EXAMPLE_PINECONE_DOCUMENTS)
    assert str(docs.documents[0].id) == EXAMPLE_PINECONE_DOCUMENT["id"]
    assert docs.documents[0].values == EXAMPLE_PINECONE_DOCUMENT["values"]
    assert str(docs.class_id) == EXAMPLE_PINECONE_DOCUMENT["id"]

EXAMPLE_METADATA_2 = copy.deepcopy(EXAMPLE_METADATA)
# change the class id for this example
EXAMPLE_METADATA_2["class_id"] = uuid.uuid4()
EXAMPLE_PINECONE_DOCUMENTS = {
    "documents": [EXAMPLE_PINECONE_DOCUMENT, EXAMPLE_PINECONE_DOCUMENT],
}

def test_different_class_ids_throws():
    """Ensure that different class ids throw an error."""
    with pytest.raises(ValueError):
        PineconeDocuments(**EXAMPLE_PINECONE_DOCUMENTS)
