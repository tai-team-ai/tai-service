"""Define tests to test the shared schemas."""
from pydantic import BaseModel
from taiservice.api.taibackend.databases.shared_schemas import (
    Metadata,
    ChunkMetadata,
)

def assert_schema_inherits(schema1: BaseModel, schema2: BaseModel) -> None:
    """Assert that schema is a subset of another schema."""
    dict_1 = schema1.schema()
    dict_2 = schema2.schema()
    assert all(key in dict_2 for key in dict_1)

def test_chunk_metadata_schema():
    """Ensure the schema doesn't change for ChunkMetadata."""
    assert_schema_inherits(ChunkMetadata, Metadata)

EXAMPLE_METADATA = {
    "title": "Example Title",
    "description": "Example Description",
    "tags": ["tag1", "tag2"],
    "resource_type": "pdf",
    "total_page_count": 10
}

def test_metadata_model():
    """Define test for Metadata model."""
    metadata = Metadata(**EXAMPLE_METADATA)
    assert metadata.title == EXAMPLE_METADATA["title"]
    assert metadata.description == EXAMPLE_METADATA["description"]
    assert metadata.tags == EXAMPLE_METADATA["tags"]
    assert metadata.resource_type == EXAMPLE_METADATA["resource_type"]
    assert metadata.total_page_count == EXAMPLE_METADATA["total_page_count"]