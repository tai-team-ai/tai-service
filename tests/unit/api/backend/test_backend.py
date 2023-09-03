"""Define tests for the backend module."""
from datetime import datetime
from uuid import uuid4
from hashlib import sha1
import pytest
from taiservice.api.routers.tai_schemas import (
    ClassResourceSnippet,
    Chat as APIChat,
    BaseChatSession as APIChatSession,
)
from taiservice.searchservice.backend.backend import (
    Backend,
    BaseClassResourceDocument,
    ClassResourceProcessingStatus,
    DBResourceMetadata
)
from taiservice.api.taibackend.taitutors.llm_schemas import (
    TaiChatSession as BEChatSession,
    BaseMessage as BEBaseMessage,
)
from taiservice.api.routers.class_resources_schema import ClassResource, ClassResourceType
from taiservice.searchservice.backend.databases.document_db_schemas import ClassResourceChunkDocument, ClassResourceDocument
from taiservice.searchservice.backend.tai_search.data_ingestor_schema import InputDocument

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

def get_valid_API_BaseClassResourceDocument_dict():
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

def get_valid_BE_BaseClassResourceDocument_dict():
    pass

def test_ClassResourceDocument_to_ClassResource():
    """Test that a ClassResourceDocument can be converted to a ClassResource."""
    base_dict = get_valid_API_BaseClassResourceDocument_dict()
    hashed_document_contents = sha1("dummy contents".encode("utf-8")).hexdigest()
    class_resource_doc = ClassResourceDocument(
        hashed_document_contents=hashed_document_contents,
        status=ClassResourceProcessingStatus.COMPLETED,
        **base_dict
    )
    api_schema = Backend.to_api_resources([class_resource_doc])
    assert len(api_schema) == 1
    assert isinstance(api_schema[0], ClassResource)


def test_ClassResourceChunkDocument_to_ClassResourceSnippet():
    """Test that a ClassResourceChunkDocument can be converted to a ClassResourceSnippet"""
    base_dict = get_valid_API_BaseClassResourceDocument_dict()
    base_dict["chunk"] = "dummy chunk"
    base_dict["metadata"]["class_id"] = base_dict["class_id"]
    class_resource_chunk_doc = ClassResourceChunkDocument(**base_dict)
    api_schema = Backend.to_api_resources([class_resource_chunk_doc])
    assert len(api_schema) == 1
    assert isinstance(api_schema[0], ClassResourceSnippet)


def test_unsupported_document_types_throw_exception():
    """Test that unsupported document types raise exception"""
    base_dict = get_valid_API_BaseClassResourceDocument_dict()
    base_doc = BaseClassResourceDocument(**base_dict)
    with pytest.raises(RuntimeError): # Assuming a RuntimeError is what's thrown for unsupported types
        Backend.to_api_resources([base_doc])

# def test_to_backend_resources():
#     """Test that API documents can be converted to database documents."""
#     api_docs = [ClassResource(**get_valid_API_BaseClassResourceDocument_dict())]
#     backend_docs = Backend.to_backend_resources(api_docs)
#     assert isinstance(backend_docs[0], BaseClassResourceDocument)

# def test_to_backend_input_docs():
#     """Test API documents can be converted to InputDocuments."""
#     resources = [ClassResource(**get_valid_API_BaseClassResourceDocument_dict())]
#     input_docs = Backend.to_backend_input_docs(resources)
#     assert isinstance(input_docs[0], InputDocument)

# def test_to_backend_chat_session():
#     """Test an API chat session can be converted to a database chat session."""
#     api_chat = APIChat(role="student", message="Hello", render_chat=True)
#     api_chat_session = APIChatSession(id=uuid4(), class_id=uuid4(), chats=[api_chat])
#     db_chat_session = Backend.to_backend_chat_session(api_chat_session)
#     assert isinstance(db_chat_session, BEChatSession)

# def test_to_backend_chat_message():
#     """Test an API chat message can be converted to a database chat message."""
#     api_chat = APIChat(role="student", message="Hello", render_chat=True)
#     db_chat = Backend.to_backend_chat_message(api_chat)
#     assert isinstance(db_chat, BEBaseMessage)

# def test_to_api_chat_session():
#     """Test a database chat session can be converted to an API chat session."""
#     be_chat = BEBaseMessage(role="student", content="Hello", render_chat=True)
#     be_chat_session = BEChatSession(id=uuid4(), class_id=uuid4(), messages=[be_chat])
#     api_chat_session = Backend.to_api_chat_session(be_chat_session)
#     assert isinstance(api_chat_session, APIChatSession)

# def test_to_api_chat_message():
#     """Test a database chat message can be converted to an API chat message."""
#     be_chat = BEBaseMessage(role="student", content="Hello", render_chat=True)
#     api_chat = Backend.to_api_chat_message(be_chat)
#     assert isinstance(api_chat, APIChat)
