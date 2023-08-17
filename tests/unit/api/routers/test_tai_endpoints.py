"""Define tests for the TAI endpoints."""
import os
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
# These must be set before importing the endpoints as the imports rely on 
# environment variables being set. I don't like this pattern, but unfortunately.
# the way pynamoDB works, rn, the config is a global model. I think we may 
# want to make it a subclass to avoid this.
os.environ["MESSAGE_ARCHIVE_BUCKET_NAME"] = "tai-service-message-archive"
os.environ["OPENAI_API_KEY_SECRET_NAME"] = "tai-service-openai-api-key"
os.environ["SEARCH_SERVICE_API_URL"] = "https://search-service-api-url"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from taiservice.api.routers.tai import (
    chat,
    search,
)
from taiservice.api.routers.tai_schemas import (
    ChatSessionRequest,
    ChatSessionResponse,
    SearchQuery,
    ResourceSearchQuery,
    SearchResults,
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

def test_search_query_example_schemas():
    """Test that the example schemas for the SearchQuery model are valid."""
    example_schema = SearchQuery.Config.schema_extra["example"]
    try:
        SearchQuery.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_resource_search_query_example_schemas():
    """Test that the example schemas for the ResourceSearchQuery model are valid."""
    example_schema = ResourceSearchQuery.Config.schema_extra["example"]
    try:
        ResourceSearchQuery.parse_obj(example_schema)
    except ValidationError as e:
        pytest.fail(f"Failed to validate example schema: {example_schema}. Error: {str(e)}")

def test_search_results_example_schemas():
    """Test that the example schemas for the SearchResults model are valid."""
    example_schema = SearchResults.Config.schema_extra["example"]
    try:
        SearchResults.parse_obj(example_schema)
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
    mock_response = SearchResults(
        suggested_resources=[],
        other_resources=[],
        **example_schema,
    )
    mock_request.app.state.tai_backend.search = MagicMock(return_value=mock_response)
    try:
        search(ResourceSearchQuery.parse_obj(example_schema), mock_request)
    except ValidationError as e:
        pytest.fail(f"Endpoint {search} failed with example schema: {example_schema}. Error: {str(e)}")

def test_search_summary_endpoint():
    """Test that the search endpoint works."""
    example_schema = SearchQuery.Config.schema_extra["example"]
    mock_request = MagicMock()
    mock_response = "Summary of results"
    mock_request.app.state.tai_backend.search = MagicMock(return_value=mock_response)
    try:
        search(SearchQuery.parse_obj(example_schema), mock_request)
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
