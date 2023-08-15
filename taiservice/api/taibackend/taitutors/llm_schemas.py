"""Define the llm schemas for interfacing with LLMs."""
import copy
from datetime import datetime
import re
from textwrap import dedent
from typing import Any, Optional, Union
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
    from ...routers.tai_schemas import ClassResourceSnippet
    from ..shared_schemas import BasePydanticModel
except (KeyError, ImportError):
    from routers.tai_schemas import ClassResourceSnippet
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
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp of the message.",
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
    arguments: dict[str, Any] = Field(
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
    class_resource_snippets: list[ClassResourceSnippet] = Field(
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
    class_name: str = Field(
        ...,
        max_length=100,
        min_length=1,
        description="The name of the class that the chat session is for.",
    )
    class_description: str = Field(
        ...,
        max_length=400,
        min_length=1,
        description="The description of the course that the chat session is for.",
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

    @property
    def last_search_query_message(self) -> Optional[SearchQuery]:
        """Return the last search query message in the chat session."""
        for message in reversed(self.messages):
            if isinstance(message, SearchQuery):
                return message
        return None

    @property
    def last_human_message(self) -> Optional[HumanMessage]:
        """Return the last human message in the chat session."""
        for message in reversed(self.messages):
            if isinstance(message, HumanMessage):
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


MARKDOWN_PROMPT = """\
Respond in markdown format with inline LaTeX support using these delimiters:
    inline: $...$ or $$...$$
    display: $$...$$
    display + equation number: $$...$$ (1)\
"""


SUMMARIZER_SYSTEM_PROMPT = f"""\
You are a summarizer. You will be given a list of documents and you're \
job is to summarize the documents in about 3-4 sentences for the user. \
{MARKDOWN_PROMPT}
Please insert equations as necessary when summarizing for the user query. \
You should not directly reference the documents in your summary. Pretend like the documents represent \
information that you already know and you are paraphrasing the information for \
the user. Remember, you must respond in markdown format with equations in LaTeX format.\
"""

SUMMARIZER_USER_PROMPT = """\
User Query:
{user_query}
Documents:
{documents}
Summary:\
"""

STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT = """\
You are a helpful assistant designed to help professors understand what \
their students are struggling with. You will be given a list of student \
interactions with a teaching assistant, and your job is to save a list \
of up to 10 most common questions ordered by most commonly asked. If there are no \
specific questions that students asked, you should try to create a list \
of questions that were implied by the student messages. For example, if \
a student says "I am struggling on homework 1", this implies that they \
are asking for help on homework 1: "Can you help me with homework 1?". \
You must respond with a list of 10 questions or less. To help the professor, \
please order the questions from most common to least common. Remember, \
you must only return a list of 10 questions so you must group similar \
questions together. You must not return more than ten questions! Here are \
the student messages:\
"""

STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT = """\
You are a helpful assistant designed to help professors understand what \
their students are struggling with. You will be given a list of student \
interactions with a teaching assistant, and your job is to create a list \
of up to 10 top discussed topics ordered by most commonly discussed. If there are no \
explicit discussion topics that students discussed, you should try to \
create a list of discussion topics that were implied by the student messages. \
You must respond with a list of 10 discussion topics or less. To help the \
professor, please order the discussion topics from most discussed by the \
students to least discussed. Please provide as much detail as possible \
for each discussion topic so that the professor can understand what the \
students were discussing. \
Remember, you must only return a list of 10 discussion topics so you must \
group similar discussion topics together. You must not return more than \
ten discussion topics! Here are the student messages:\
"""

FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT = """\
Please condense this list by grouping by topic, using 'and' where necessary to combine:\
"""


STEERING_PROMPT = """\
Thought: I don't know anything about what the user is asking because I am a tutor for '{class_name}'. \
I must be honest with the student and tell them that I don't know about that concept \
because it is not related to '{class_name}' and I should suggest that they use Google to find more info or instruct them to ask \
their Instructor or TA for further help.\
"""

BASE_SYSTEM_MESSAGE = f"""\
You are a friendly tutor named {{name}} that tutors for a class called '{{class_name}}'. As {{name}}, {{persona}}. \
You are to be a good listener and ask how you can help the student and be there for them. \
You MUST get to know them as a human being and understand their needs in order to be successful. \
To do this, you need to ask questions to understand the student as best as possible. \
{MARKDOWN_PROMPT}
The student has requested that you use responses with a technical level of a {{technical_level}} to help the understand the material. \
Remember, you should explain things in a way that a {{technical_level}} would understand. \
Remember, your name is {{name}} and {{persona}}. At times, you may not know the answer to a question \
because you are a tutor only for '{{class_name}}'. That's okay! If this occurs you should prompt the student \
to reach out to their professor or TA.\
"""

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
    def get_system_prompt(name: TaiTutorName, technical_level: ResponseTechnicalLevel, class_name: str) -> str:
        """Get the system prompt for the given name."""
        tai_profile = TaiProfile.get_profile(name)
        technical_level_str = RESPONSE_TECHNICAL_LEVEL_MAPPING[technical_level]
        format_string = ValidatedFormatString(
            format_string=BASE_SYSTEM_MESSAGE,
            kwargs={
                "technical_level": technical_level_str,
                "class_name": class_name,
                **tai_profile.dict(),
            },
        )
        return format_string.format()
