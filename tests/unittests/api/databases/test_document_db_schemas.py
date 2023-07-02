"""Define tests for testing the indexer."""
import pytest
from pydantic import ValidationError
from tests.unittests.api.databases.test_shared_schemas import (
    assert_schema2_inherits_from_schema1,
    EXAMPLE_METADATA,
)
from taiservice.api.taibackend.databases.document_db_schemas import (
    ClassResourceProcessingStatus,
    BaseClassResourceDocument,
    ClassResourceDocument,
    ClassResourceChunkDocument,
)


def test_class_resource_chunk_document_schema():
    """Ensure the schema doesn't change for ClassResourceChunkDocument."""
    assert_schema2_inherits_from_schema1(ClassResourceChunkDocument, BaseClassResourceDocument)

def test_class_resource_document_schema():
    """Ensure the schema doesn't change for ClassResourceDocument."""
    assert_schema2_inherits_from_schema1(ClassResourceDocument, BaseClassResourceDocument)


EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "class_id": "123e4567-e89b-12d3-a456-426614174000",
    "full_resource_url": "https://example.com/resource",
    "metadata": EXAMPLE_METADATA
}

def test_if_completed_must_have_chunk_ids():
    """Ensure that the chunk ids must not be empty if the status is completed."""
    with pytest.raises(ValidationError) as e:
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.COMPLETED,
            chunk_vector_ids=[],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )

def test_if_completed_must_have_vector_ids():
    """Ensure that the chunk ids must not be empty if the status is completed."""
    with pytest.raises(ValidationError) as e:
        ClassResourceDocument(
            status=ClassResourceProcessingStatus.COMPLETED,
            chunk_vector_ids=[],
            **EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT
        )

def test_base_class_resource_document_model():
    """Define test for BaseClassResourceDocument model."""
    doc = BaseClassResourceDocument(**EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT)
    assert str(doc.id) == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["id"]
    assert str(doc.class_id) == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["class_id"]
    assert doc.full_resource_url == EXAMPLE_BASE_CLASS_RESOURCE_DOCUMENT["full_resource_url"]
