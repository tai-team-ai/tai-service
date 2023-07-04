"""Define tests to test the shared schemas."""
from pydantic import BaseModel
from taiservice.api.taibackend.databases.shared_schemas import (
    Metadata,
    BasePydanticModel,
)

def assert_schema1_inherits_from_schema2(schema1: BaseModel, schema2: BaseModel) -> None:
    """Assert that schema is a subset of another schema."""
    schema1_attrs = set(schema1.__fields__.keys())
    schema2_attrs = set(schema2.__fields__.keys())
    assert schema2_attrs.issubset(schema1_attrs)

def test_metadata_schema():
    """Ensure the schema doesn't change for Metadata."""
    assert_schema1_inherits_from_schema2(Metadata, BasePydanticModel)

EXAMPLE_METADATA = {
    "title": "Example Title",
    "description": "Example Description",
    "tags": ["tag1", "tag2"],
    "resource_type": "textbook",
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
