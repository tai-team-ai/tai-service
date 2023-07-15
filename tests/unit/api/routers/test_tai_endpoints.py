"""Define tests for the TAI endpoints."""
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from taiservice.api.routers.tai import (
    chat,
    search,
)
from taiservice.api.routers.tai_schemas import (
    ChatSessionRequest,
    ChatSessionResponse,
    ResourceSearchQuery,
    ResourceSearchAnswer,
    TaiTutorChat,
    TaiTutorName as ApiTaiTutorName,
    ResponseTechnicalLevel as ApiTechnicalLevel,
)
from taiservice.api.taibackend.taitutors.llm_schemas import (
    TaiTutorName as BETaiTutorName,
    ResponseTechnicalLevel as BETechnicalLevel,
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
        ChatSessionResponse(**example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_resource_search_query_example_schemas():
    """Test that the example schemas for the ResourceSearchQuery model are valid."""
    example_schema = ResourceSearchQuery.Config.schema_extra["example"]
    try:
        ResourceSearchQuery.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_resource_search_answer_example_schemas():
    """Test that the example schemas for the ResourceSearchAnswer model are valid."""
    example_schema = ResourceSearchAnswer.Config.schema_extra["example"]
    try:
        ResourceSearchAnswer.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_chat_endpoint():
    """Test that the chat endpoint works."""
    example_schema = ChatSessionRequest.Config.schema_extra["example"]
    mock_request = MagicMock()
    mock_chat_session = ChatSessionRequest(**example_schema)
    mock_chat_session.chats.append(
        TaiTutorChat(
            message="Hello!",
            class_resource_snippets=[],
            render_chat=True,
            tai_tutor=ApiTaiTutorName.FINN,
            technical_level=ApiTechnicalLevel.EXPLAIN_LIKE_IM_5,
        )
    )
    mock_response = ChatSessionResponse.parse_obj(mock_chat_session)
    mock_request.app.state.tai_backend.get_tai_response = MagicMock(return_value=mock_response)
    try:
        chat(ChatSessionRequest.parse_obj(example_schema), mock_request)
    except ValidationError as e:
        pytest.fail(f"Endpoint {chat} failed with example schema: {example_schema}. Error: {str(e)}")

def test_search_endpoint():
    """Test that the search endpoint works."""
    example_schema = ResourceSearchQuery.Config.schema_extra["example"]
    mock_request = MagicMock()
    mock_response = ResourceSearchAnswer(
        summary_snippet="This is a summary snippet.",
        suggested_resources=[],
        other_resources=[],
        **example_schema,
    )
    mock_request.app.state.tai_backend.search = MagicMock(return_value=mock_response)
    try:
        search(ResourceSearchQuery.parse_obj(example_schema), mock_request)
    except ValidationError as e:
        pytest.fail(f"Endpoint {search} failed with example schema: {example_schema}. Error: {str(e)}")

def test_tai_tutor_names_match_backend():
    """Test that the resource types match the backend."""
    api_schema = ApiTaiTutorName.__members__
    backend_schema = BETaiTutorName.__members__
    assert api_schema == backend_schema

def test_class_resource_status_match_backend():
    """Test that the class resource status match the backend."""
    api_schema = ApiTechnicalLevel.__members__
    backend_schema = BETechnicalLevel.__members__
    assert api_schema == backend_schema
