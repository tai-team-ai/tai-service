"""Define tests for the common resources endpoints."""
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from pydantic import ValidationError
from taiservice.api.routers.common_resources_schema import (
    FrequentlyAccessedResources,
    CommonQuestions,
)
from taiservice.api.routers.common_resources import (
    get_frequently_accessed_resources,
    get_common_questions,
)


def test_common_resources_example_schemas():
    """Test that the example schemas for the CommonResources model are valid."""
    example_schema = FrequentlyAccessedResources.Config.schema_extra["example"]
    try:
        FrequentlyAccessedResources.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_get_common_resources_endpoint():
    """Test that the get common resources endpoint works."""
    example_schema = FrequentlyAccessedResources.Config.schema_extra["example"]
    request_mock = MagicMock()
    try:
        get_frequently_accessed_resources(request_mock, uuid4())
    except ValidationError as e:
        pytest.fail(f"Endpoint {get_frequently_accessed_resources} failed with example schema: {example_schema}. Error: {str(e)}")

def test_common_questions_example_schemas():
    """Test that the example schemas for the CommonQuestions model are valid."""
    example_schema = CommonQuestions.Config.schema_extra["example"]
    try:
        CommonQuestions.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_get_common_questions_endpoint():
    """Test that the get common questions endpoint works."""
    example_schema = CommonQuestions.Config.schema_extra["example"]
    request_mock = MagicMock()
    try:
        get_common_questions(request_mock, uuid4())
    except ValidationError as e:
        pytest.fail(f"Endpoint {get_common_questions} failed with example schema: {example_schema}. Error: {str(e)}")
