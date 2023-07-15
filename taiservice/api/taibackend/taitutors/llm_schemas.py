"""Define the llm schemas for interfacing with LLMs."""
import copy
import re
from textwrap import dedent
from typing import Optional, Union
from enum import Enum
from uuid import UUID
from uuid import uuid4
from pydantic import Field, BaseModel, validator
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

    MILO = "Milo"
    DECLAN = "Declan"
    FINN = "Finn"
    ADA = "Ada"
    REMY = "Remy"
    KAI = "Kai"
    VIOLET = "Violet"

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


BASE_SYSTEM_MESSAGE = dedent("""\

""")


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

class SearchQuery(BaseMessage, HumanMessage):
    """Define the model for the search query."""
    role: ChatRole = Field(
        default=ChatRole.STUDENT,
        const=True,
        description="The role of the creator of the chat message.",
    )



class TutorAndStudentBaseMessage(BaseMessage):
    """Define the base message for the TAI tutor and student."""
    tai_tutor_name: TaiTutorName = Field(
        default=TaiTutorName.FINN,
        description="The name of the TAI tutor that generated this message.",
    )
    technical_level: ResponseTechnicalLevel = Field(
        default=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        description="The technical level of the response.",
    )


class StudentMessage(HumanMessage, TutorAndStudentBaseMessage):
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

class TaiTutorMessage(AIMessage, TutorAndStudentBaseMessage):
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

    @staticmethod
    def from_prompt(prompt: str) -> "SystemMessage":
        """Create a system message from a prompt."""
        return SystemMessage(
            text=prompt,
            role=ChatRole.TAI_TUTOR,
            render_chat=False,
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

    def insert_system_prompt(self, prompt: str) -> None:
        """Insert a system prompt to the beginning of the chat session."""
        if self.messages and isinstance(self.messages[0], SystemMessage):
            self.messages[0].content = prompt
        else:
            self.messages.insert(0, SystemMessage(content=prompt))

    def remove_system_prompt(self) -> None:
        """Remove the system prompt from the beginning of the chat session."""
        if self.messages and isinstance(self.messages[0], SystemMessage):
            self.messages.pop(0)

    @staticmethod
    def from_message(message: BaseMessage, class_id: UUID) -> "TaiChatSession":
        """Create a new chat session from a message."""
        return TaiChatSession(
            id=uuid4(),
            class_id=class_id,
            messages=[message],
        )


class ValidatedFormatString(BasePydanticModel):
    """Define the model for the key safe format string."""
    format_string: str = Field(
        ...,
        description="The format string.",
    )
    kwargs: dict[str, str] = Field(
        ...,
        description="The keys in the format string.",
    )

    @validator("kwargs")
    def validate_keys(cls, keys: dict[str, str], values: dict) -> dict[str, str]:
        """Validate the keys and ensure all are in the format string and there are no extra keys in format string."""
        format_string_keys = re.findall(r"\{([a-zA-Z0-9_]+)\}", values["format_string"])
        for key in keys:
            if key not in format_string_keys:
                raise ValueError(f"Key {key} in keys not found in format string.")
        for key in format_string_keys:
            if key not in keys:
                raise ValueError(f"Key {key} in format string not found in keys.")
        return keys

    def format(self) -> str:
        """Format the format string."""
        return self.format_string.format(**self.kwargs)

SUMMARIZER_SYSTEM_PROMPT = dedent(
    """You are a summarizer. You will be given a search query and a list of documents. You're
    job is to summarize the documents. If you are not provided a list of documents, you should 
    not respond with anything."""
)
SUMMARIZER_USER_PROMPT = dedent("""\
Student search query: {search_query}
Returned search result documents:
{documents}
Snippet (Summary of the search results):
""")

BASE_SYSTEM_MESSAGE = dedent("""\
You are a friendly tutor named {name} that works for T.A.I. As {name}, {persona}. \
You are to be a good listener and ask how you can help the student and be there for them. \
You MUST get to know them as a human being and understand their needs in order to be successful. \
To do this, you need to ask questions to understand the student as best as possible. \
If a student asks for help, you should NOT give the student answers or solve the problem for them. \
Instead, you should help them understand the material and guide them to the answer step by step. \
Each step you send should be in it's own message and not all in the same message. \
For example, if the student asks for help, you could ask them what they have tried so far and suggest what they should try next. \
You should progressively give more information to the student until they understand the material and not give them all in one message. \
The student has requested that you use responses with a technical level of a {technical_level} to help the understand the material. \
Remember, you should explain things in a way that a {technical_level} would understand. \
Most importantly, you are not to give the student answers even if they ask for them, however, you can give them hints.\
""")

MILO = {
    "name": TaiTutorName.MILO.value,
    "persona": "you are are less formal in how you talk and are technically savvy. You never resist the urge to incorporate real-world examples into your explanations.",
}
DECLAN = {
    "name": TaiTutorName.DECLAN.value,
    "persona": "you have a balanced conversational style and are really creative. You love thinking outside the box and are always looking for new ways to explain things.",
}
FINN = {
    "name": TaiTutorName.FINN.value,
    "persona": "you are informal and are very empathetic. You looove to weave narratives into your explanations and are always looking for ways to make things more relatable.",
}
ADA = {
    "name": TaiTutorName.ADA.value,
    "persona": "you slightly informal, but highly creative. You love to ask questions that might seem random, but are actually very insightful to help connect dots for the student.",
}
REMY = {
    "name": TaiTutorName.REMY.value,
    "persona": "you are very informal and highly creative. You love artsy things and are always looking for ways to make things more relatable.",
}
KAI = {
    "name": TaiTutorName.KAI.value,
    "persona": "you are formal, but still bring some creativity. You excel at diving deep on technical topics and are always looking to nerd out with the student.",
}
VIOLET = {
    "name": TaiTutorName.VIOLET.value,
    "persona": "you are formal and very technical. You are very good at explaining technical topics and are always looking to nerd out with the student.",
}
RESPONSE_TECHNICAL_LEVEL_MAPPING = {
    ResponseTechnicalLevel.EXPLAIN_LIKE_IM_5: "5 year old",
    ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL: "high school student",
    ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_COLLEGE: "college student",
    ResponseTechnicalLevel.EXPLAIN_LIKE_IM_AN_EXPERT_IN_THE_FIELD: "expert in the field",
}

class TaiProfile(BasePydanticModel):
    """Define the model for the TAI profile."""
    name: TaiTutorName = Field(
        ...,
        description="The name of the tutor.",
    )
    persona: str = Field(
        ...,
        description="The persona of the tutor.",
    )

    @staticmethod
    def get_profile(name: TaiTutorName) -> "TaiProfile":
        """Get the profile for the given name."""
        if name == TaiTutorName.MILO:
            return TaiProfile(**MILO)
        elif name == TaiTutorName.DECLAN:
            return TaiProfile(**DECLAN)
        elif name == TaiTutorName.FINN:
            return TaiProfile(**FINN)
        elif name == TaiTutorName.ADA:
            return TaiProfile(**ADA)
        elif name == TaiTutorName.REMY:
            return TaiProfile(**REMY)
        elif name == TaiTutorName.KAI:
            return TaiProfile(**KAI)
        elif name == TaiTutorName.VIOLET:
            return TaiProfile(**VIOLET)
        else:
            raise ValueError(f"Invalid tutor name {name}.")

    @staticmethod
    def get_system_prompt(name: TaiTutorName, technical_level: ResponseTechnicalLevel) -> str:
        """Get the system prompt for the given name."""
        tai_profile = TaiProfile.get_profile(name)
        technical_level_str = RESPONSE_TECHNICAL_LEVEL_MAPPING[technical_level]
        format_string = ValidatedFormatString(
            format_string=BASE_SYSTEM_MESSAGE,
            kwargs={**tai_profile.dict(), "technical_level": technical_level_str},
        )
        return format_string.format()
