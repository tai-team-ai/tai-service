"""Define tests for the TAI endpoints."""
import pytest
from pydantic import ValidationError
from taiservice.api.routers.class_resources import (
    ClassResources,
    get_class_resources,
    create_class_resource,
)

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
