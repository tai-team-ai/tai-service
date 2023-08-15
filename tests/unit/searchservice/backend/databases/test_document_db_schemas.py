"""Define tests for testing the tai_search."""
from hashlib import sha1
import pytest
from pydantic import ValidationError
from tests.unit.searchservice.backend.databases.test_shared_schemas import (
    assert_schema1_inherits_from_schema2,
    EXAMPLE_METADATA,
)
from taiservice.searchservice.backend.databases.document_db_schemas import (
    ClassResourceProcessingStatus,
    BaseClassResourceDocument,
    ClassResourceDocument,
    ClassResourceChunkDocument,
)


def test_class_resource_chunk_document_schema():
    """Ensure the schema doesn't change for ClassResourceChunkDocument."""
    assert_schema1_inherits_from_schema2(ClassResourceChunkDocument, BaseClassResourceDocument)

def test_class_resource_document_schema():
    """Ensure the schema doesn't change for ClassResourceDocument."""
    assert_schema1_inherits_from_schema2(ClassResourceDocument, BaseClassResourceDocument)


EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "class_id": "123e4567-e89b-12d3-a456-426614174000",
    "full_resource_url": "https://example.com/resource",
    "preview_image_url": "https://example.com/resource",
    "usage_log": [],
    "metadata": EXAMPLE_METADATA
}
def test_base_class_resource_document_model():
    """Define test for BaseClassResourceDocument model."""
    doc = BaseClassResourceDocument(**EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT)
    assert str(doc.id) == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["id"]
    assert str(doc.class_id) == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["class_id"]
    assert doc.full_resource_url == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["full_resource_url"]
    assert doc.metadata.dict(serialize_nums=False) == EXAMPLE_METADATA

def test_if_completed_must_have_chunk_ids():
    """Ensure that the chunk ids must not be empty if the status is completed."""
    with pytest.raises(ValidationError):
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.COMPLETED,
            class_resource_chunk_ids=[],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )

def test_if_completed_must_have_vector_ids():
    """Ensure that the chunk ids must not be empty if the status is completed."""
    with pytest.raises(ValidationError):
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.COMPLETED,
            class_resource_chunk_ids=[],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )

CLASS_RESOURCE_DOCUMENT = {
    "status": ClassResourceProcessingStatus.COMPLETED,
    "class_resource_chunk_ids": ["123e4567-e89b-12d3-a456-426614174000"],
    "create_timestamp": "2021-01-01 00:00:00",
    "modified_timestamp": "2021-01-01 00:00:00",
    "child_resource_ids": ["123e4567-e89b-12d3-a456-426614174000"],
    "parent_resource_ids": ["123e4567-e89b-12d3-a456-426614174000"],
    "hashed_document_contents": sha1(b"test").hexdigest(),
    **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
}
def test_class_resource_document_model():
    """Define test for ClassResourceDocument model."""
    doc = ClassResourceDocument(**CLASS_RESOURCE_DOCUMENT)
    del CLASS_RESOURCE_DOCUMENT["modified_timestamp"]
    dict_ = doc.dict(serialize_dates=True, exclude={"modified_timestamp"}, serialize_nums=False)
    assert dict_ == CLASS_RESOURCE_DOCUMENT
