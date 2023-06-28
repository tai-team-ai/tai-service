"""Define tests for the TAI endpoints."""
import pytest
from pydantic import ValidationError
from taiservice.api.routers.tai import (
    ChatSession,
    ResourceSearchQuery,
)

def test_chat_session_example_schemas():
    """Test that the example schemas for the ChatSession model are valid."""
    example_schemas = ChatSession.Config.schema_extra["examples"]
    for example_schema in example_schemas:
        try:
            ChatSession.parse_obj(example_schema)
        except ValidationError as e:
            pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_resource_search_query_example_schemas():
    """Test that the example schemas for the ResourceSearchQuery model are valid."""
    example_schemas = ResourceSearchQuery.Config.schema_extra["examples"]
    for example_schema in example_schemas:
        try:
            ResourceSearchQuery.parse_obj(example_schema)
        except ValidationError as e:
            pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")
