"""Define tests for the common resources endpoints."""
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from taiservice.api.routers.common_resources_schema import (
    CommonResources,
    CommonQuestions,
)
from taiservice.api.routers.common_resources import (
    get_common_resources,
    get_common_questions,
)


def test_common_resources_example_schemas():
    """Test that the example schemas for the CommonResources model are valid."""
    example_schema = CommonResources.Config.schema_extra["example"]
    try:
        CommonResources.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_get_common_resources_endpoint():
    """Test that the get common resources endpoint works."""
    example_schema = CommonResources.Config.schema_extra["example"]
    request_mock = MagicMock()
    try:
        get_common_resources(request_mock)
    except ValidationError as e:
        pytest.fail(f"Endpoint {get_common_resources} failed with example schema: {example_schema}. Error: {str(e)}")

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
        get_common_questions(request_mock)
    except ValidationError as e:
        pytest.fail(f"Endpoint {get_common_questions} failed with example schema: {example_schema}. Error: {str(e)}")
