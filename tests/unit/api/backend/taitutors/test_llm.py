"""Define tests for the tai tutor llm."""
from unittest.mock import MagicMock, patch
from taiservice.api.taibackend.taitutors.llm import TaiLLM, TaiChatSession, ChatOpenAIConfig, Archive


def get_llm_config() -> ChatOpenAIConfig:
    """Get a ChatOpenAIConfig object."""
    return ChatOpenAIConfig(
        api_key="api_key",
        request_timeout=10,
        message_archive=MagicMock(spec=Archive),
    )


def test_add_tai_tutor_chat_response_calls_archive_message_with_correct_params():
    """Test add_tai_tutor_chat_response method calls archive_message with correct parameters."""
    
    # Mock Archive and its method archive_message
    archive_mock = MagicMock(spec=Archive)
    
    config = get_llm_config()

    # Set the mock Archive object to the config
    config.message_archive = archive_mock

    llm = TaiLLM(config)

    # Mock TaiChatSession
    chat_session_mock = MagicMock(spec=TaiChatSession)
    chat_session_mock.last_student_message = "dummy_message"
    chat_session_mock.class_id = "dummy_class_id"

    # Mock the _append_model_response method in the llm instance
    with patch.object(llm, '_append_model_response', autospec=True):

        # Call the add_tai_tutor_chat_response method with the mocked TaiChatSession
        llm.add_tai_tutor_chat_response(chat_session_mock)

        # Assert that the archive_message method in the _archive attribute is called with correct parameters
        archive_mock.archive_message.assert_called_once_with("dummy_message", "dummy_class_id")
