"""Define tests for testing the indexer."""
import pytest
from pydantic import BaseModel

from taiservice.api.taibackend.indexer.schemas import (
    ClassResourceProcessingStatus,
    Metadata,
    BaseClassResourceDocument,
    ClassResourceDocument,
    ChunkMetadata,
    ClassResourceChunkDocument,
)

def assert_schema_inherits(schema1: BaseModel, schema2: BaseModel) -> None:
    """Assert that schema is a subset of another schema."""
    dict_1 = schema1.schema()
    dict_2 = schema2.schema()
    assert all(key in dict_2 for key in dict_1)

def test_chunk_metadata_schema():
    """Ensure the schema doesn't change for ChunkMetadata."""
    assert_schema_inherits(ChunkMetadata, Metadata)

def test_class_resource_chunk_document_schema():
    """Ensure the schema doesn't change for ClassResourceChunkDocument."""
    assert_schema_inherits(ClassResourceChunkDocument, BaseClassResourceDocument)

def test_class_resource_document_schema():
    """Ensure the schema doesn't change for ClassResourceDocument."""
    assert_schema_inherits(ClassResourceDocument, BaseClassResourceDocument)

def test_if_chunk_ids_status_must_be_completed():
    """Ensure that the chunk ids must not be empty if the status is completed."""
    with pytest.raises(ValueError) as e:
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.COMPLETED,
            class_resource_chunk_ids=[],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )
    assert "The class resource chunk ids must NOT be empty if the status is completed." in str(e.value)

def test_if_not_chunk_ids_status_must_not_be_completed():
    """Ensure that the chunk ids must be empty if the status is not completed."""
    with pytest.raises(ValueError) as e:
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.PROCESSING,
            class_resource_chunk_ids=["123e4567-e89b-12d3-a456-426614174000"],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )
    assert "The class resource chunk ids must be empty if the status is NOT completed." in str(e.value)

EXAMPLE_METADATA = {
    "title": "Example Title",
    "description": "Example Description",
    "tags": ["tag1", "tag2"],
    "resource_type": "pdf",
    "total_page_count": 10
}
EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "class_id": "example_class_id",
    "full_resource_url": "https://example.com/resource",
    "metadata": EXAMPLE_METADATA
}

def test_metadata_model():
    """Define test for Metadata model."""
    metadata = Metadata(**EXAMPLE_METADATA)
    assert metadata.title == "Example Title"
    assert metadata.description == "Example Description"
    assert metadata.tags == ["tag1", "tag2"]
    assert metadata.resource_type == "pdf"
    assert metadata.total_page_count == 10

def test_base_class_resource_document_model():
    """Define test for BaseClassResourceDocument model."""
    doc = BaseClassResourceDocument(**EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT)
    assert str(doc.id) == "123e4567-e89b-12d3-a456-426614174000"
    assert doc.class_id == "example_class_id"
    assert doc.full_resource_url == "https://example.com/resource"
    assert doc.metadata.title == "Example Title"
    assert doc.metadata.description == "Example Description"
    assert doc.metadata.tags == ["tag1", "tag2"]
    assert doc.metadata.resource_type == "pdf"
    assert doc.metadata.total_page_count == 10