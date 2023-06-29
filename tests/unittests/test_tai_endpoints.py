"""Define tests for the TAI endpoints."""
import pytest
from pydantic import ValidationError
from taiservice.api.routers.tai import (
    ChatSessionRequest,
    ChatSessionResponse,
    ResourceSearchQuery,
)

def test_chat_session_request_example_schemas():
    """Test that the example schemas for the ChatSession model are valid."""
    example_schema = ChatSessionRequest.Config.schema_extra["example"]
    try:
        ChatSessionRequest.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_chat_session_response_example_schemas():
    """Test that the example schemas for the ChatSession model are valid."""
    example_schema = ChatSessionResponse.Config.schema_extra["example"]
    try:
        ChatSessionResponse.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")


def test_resource_search_query_example_schemas():
    """Test that the example schemas for the ResourceSearchQuery model are valid."""
    example_schema = ResourceSearchQuery.Config.schema_extra["example"]
    try:
        ResourceSearchQuery.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")
