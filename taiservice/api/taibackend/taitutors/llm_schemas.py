"""Define the llm schemas for interfacing with LLMs."""
import copy
from typing import Any, Optional, Union
from enum import Enum
from uuid import UUID
from pydantic import Field, BaseModel
from langchain.schema import (
    AIMessage,
    FunctionMessage as langchainFunctionMessage,
    HumanMessage,
    SystemMessage as langchainSystemMessage,
    BaseMessage as langchainBaseMessage,
)
# first imports for local development, second imports for deployment
try:
    from ..databases.document_db_schemas import ClassResourceChunkDocument
    from ..shared_schemas import BasePydanticModel
except (KeyError, ImportError):
    from taibackend.databases.document_db_schemas import ClassResourceChunkDocument
    from taibackend.shared_schemas import BasePydanticModel

class TaiTutorName(str, Enum):
    """Define the supported TAI tutors."""

    FIN = "fin"
    ALEX = "alex"
    NA = "na"

class ChatRole(str, Enum):
    """Define the built-in MongoDB roles."""

    TAI_TUTOR = "taiTutor"
    STUDENT = "student"
    FUNCTION = "function"

class ResponseTechnicalLevel(str, Enum):
    """Define the technical level of the response."""

    EXPLAIN_LIKE_IM_5 = "like5"
    EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL = "likeHighSchool"
    EXPLAIN_LIKE_IM_IN_COLLEGE = "likeCollege"
    EXPLAIN_LIKE_IM_AN_EXPERT_IN_THE_FIELD = "likeExpertInTheField"

class BaseMessage(langchainBaseMessage):
    """Define the base message for the TAI tutor."""

    role: ChatRole = Field(
        ...,
        description="The role of the user that generated this message.",
    )
    render_chat: bool = Field(
        default=True,
        description="Whether or not to render the chat message. If false, the chat message will be hidden from the student.",
    )

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "base"

class TutorStudentBaseMessage(BaseMessage):
    """Define the base message for the TAI tutor and student."""
    tai_tutor_name: TaiTutorName = Field(
        ...,
        description="The name of the TAI tutor that generated this message.",
    )
    technical_level: ResponseTechnicalLevel = Field(
        default=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        description="The technical level of the response.",
    )


class StudentMessage(HumanMessage, TutorStudentBaseMessage):
    """Define the model for the student chat message."""

    role: ChatRole = Field(
        default=ChatRole.STUDENT,
        const=True,
        description="The role of the creator of the chat message.",
    )

class AIResponseCallingFunction(BaseModel):
    """Define the model for the AI response calling function."""

    name: str = Field(
        ...,
        description="The name of the function to call.",
    )
    arguments: str = Field(
        ...,
        description="The arguments to pass to the function.",
    )

class TaiTutorMessage(AIMessage, TutorStudentBaseMessage):
    """Define the model for the TAI tutor chat message."""

    role: ChatRole = Field(
        default=ChatRole.TAI_TUTOR,
        const=True,
        description="The role of the creator of the chat message.",
    )
    class_resource_chunks: list[ClassResourceChunkDocument] = Field(
        default=[],
        description="The class resource chunks that were used to generate this message, if any.",
    )
    function_call: Optional[AIResponseCallingFunction] = Field(
        default=None,
        description="The function call that the assistant wants to make.",
    )

class SystemMessage(langchainSystemMessage, BaseMessage):
    """Define the model for the system chat message."""

    role: ChatRole = Field(
        default=ChatRole.TAI_TUTOR,
        const=True,
        description="The role of the creator of the chat message.",
    )
    render_chat: bool = Field(
        default=False,
        const=True,
        description="System messages are never rendered. Therefore this field is always false.",
    )

class FunctionMessage(langchainFunctionMessage, BaseMessage):
    """Define the model for the function chat message."""

    role: ChatRole = Field(
        default=ChatRole.FUNCTION,
        const=True,
        description="The role of the creator of the chat message.",
    )
    render_chat: bool = Field(
        default=False,
        const=True,
        description="Function messages are never rendered. Therefore this field is always false.",
    )


class TaiChatSession(BasePydanticModel):
    """Define the model for the TAI chat session. Compatible with LangChain."""
    id: UUID = Field(
        ...,
        description="The ID of the chat session.",
    )
    class_id: UUID = Field(
        ...,
        description="The class ID to which this chat session belongs.",
    )
    messages: list[BaseMessage] = Field(
        default_factory=list,
        description="The messages in the chat session.",
    )

    class Config:
        """Define the config for the model."""
        validate_assignment = True

    @property
    def last_chat_message(self) -> Optional[BaseMessage]:
        """Return the last chat message in the chat session."""
        if self.messages:
            return self.messages[-1]
        return None

    @property
    def last_student_message(self) -> Optional[StudentMessage]:
        """Return the last student message in the chat session."""
        for message in reversed(self.messages):
            if isinstance(message, StudentMessage):
                return message
        return None

    def append_chat_messages(self, new_messages: Union[list[BaseMessage], BaseMessage]) -> None:
        """Append a chat message to the chat session."""
        if isinstance(new_messages, BaseMessage):
            new_messages = [new_messages]
        msgs = copy.deepcopy(self.messages)
        msgs.extend(new_messages)
        self.messages = msgs
