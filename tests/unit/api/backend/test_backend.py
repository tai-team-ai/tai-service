"""Define tests for the backend module."""
from datetime import datetime
from uuid import uuid4
from hashlib import sha1
import pytest
from taiservice.api.routers.tai_schemas import ClassResourceSnippet
from taiservice.api.taibackend.backend import (
    Backend,
    BaseClassResourceDocument,
    ClassResourceProcessingStatus,
    DBResourceMetadata
)
from taiservice.api.routers.class_resources_schema import ClassResource, ClassResourceType
from taiservice.api.taibackend.databases.document_db_schemas import ClassResourceChunkDocument, ClassResourceDocument

def get_valid_metadata_dict():
    """Get a valid metadata dictionary"""
    base_dict = {
        "title": "dummy title",
        "description": "dummy description",
        "tags": ["dummy", "tags"],
        "resource_type": ClassResourceType.TEXTBOOK,
    }
    DBResourceMetadata(**base_dict)
    return base_dict

def get_valid_BaseClassResourceDocument_dict():
    """Get a valid dictionary for BaseClassResourceDocument initialization."""
    valid_metadata = get_valid_metadata_dict()
    base_dict = {
        "id": uuid4(),
        "class_id": uuid4(),
        "full_resource_url": "https://example.com",
        "preview_image_url": "https://example.com",
        "metadata": valid_metadata,
        "create_timestamp": datetime.utcnow(),
        "modified_timestamp": datetime.utcnow()
    }
    BaseClassResourceDocument(**base_dict)
    return base_dict


def test_ClassResourceDocument_to_ClassResource():
    """Test that a ClassResourceDocument can be converted to a ClassResource."""
    base_dict = get_valid_BaseClassResourceDocument_dict()
    hashed_document_contents = sha1("dummy contents".encode("utf-8")).hexdigest()
    class_resource_doc = ClassResourceDocument(
        hashed_document_contents=hashed_document_contents,
        status=ClassResourceProcessingStatus.COMPLETED,
        **base_dict
    )
    api_schema = Backend.to_api_schema([class_resource_doc])
    assert len(api_schema) == 1
    assert isinstance(api_schema[0], ClassResource)


def test_ClassResourceChunkDocument_to_ClassResourceSnippet():
    """Test that a ClassResourceChunkDocument can be converted to a ClassResourceSnippet"""
    base_dict = get_valid_BaseClassResourceDocument_dict()
    base_dict["chunk"] = "dummy chunk"
    base_dict["metadata"]["class_id"] = base_dict["class_id"]
    class_resource_chunk_doc = ClassResourceChunkDocument(**base_dict)
    api_schema = Backend.to_api_schema([class_resource_chunk_doc])
    assert len(api_schema) == 1
    assert isinstance(api_schema[0], ClassResourceSnippet)


def test_unsupported_document_types_throw_exception():
    """Test that unsupported document types raise exception"""
    base_dict = get_valid_BaseClassResourceDocument_dict()
    base_doc = BaseClassResourceDocument(**base_dict)
    with pytest.raises(RuntimeError): # Assuming a RuntimeError is what's thrown for unsupported types
        Backend.to_api_schema([base_doc])
