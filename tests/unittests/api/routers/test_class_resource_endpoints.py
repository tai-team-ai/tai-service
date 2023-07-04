"""Define tests for the TAI endpoints."""
import pytest
from pydantic import ValidationError
from taiservice.api.taibackend.databases import shared_schemas as backend_shared_schemas
from taiservice.api.taibackend.databases import document_db_schemas as backend_db_schemas
from taiservice.api.routers.class_resources import (
    ClassResources,
    get_class_resources,
    create_class_resource,
)
from taiservice.api.routers import class_resources as class_resources_router


def test_class_resource_example_schemas():
    """Test that the example schemas for the ChatSession model are valid."""
    example_schema = ClassResources.Config.schema_extra["example"]
    try:
        ClassResources.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_get_class_resources_endpoint():
    """Test that the search endpoint works."""
    try:
        get_class_resources()
    except ValidationError as e:
        pytest.fail(f"Endpoint {get_class_resources} failed. Error: {str(e)}")

def test_create_class_resource_endpoint():
    """Test that the search endpoint works."""
    example_schema = ClassResources.Config.schema_extra["example"]
    try:
        create_class_resource(ClassResources.parse_obj(example_schema))
    except ValidationError as e:
        pytest.fail(f"Endpoint {create_class_resource} failed with example schema: {example_schema}. Error: {str(e)}")

def test_resource_types_match_backend():
    """Test that the resource types match the backend."""
    api_schema = class_resources_router.ClassResourceType.__members__
    backend_schema = backend_shared_schemas.ClassResourceType.__members__
    assert api_schema == backend_schema

def test_class_resource_status_match_backend():
    """Test that the class resource status match the backend."""
    api_schema = class_resources_router.ClassResourceProcessingStatus.__members__
    backend_schema = backend_db_schemas.ClassResourceProcessingStatus.__members__
    assert api_schema == backend_schema
