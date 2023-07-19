"""Define the llms interface used for the TAI chat backend."""
from enum import Enum
import json
from typing import Optional
from uuid import UUID
from uuid import uuid4
from langchain.chat_models import ChatOpenAI
from langchain import PromptTemplate
from langchain.chat_models.base import BaseChatModel
from langchain.chains.openai_functions.base import create_openai_fn_chain
from pydantic import Field
# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import BaseOpenAIConfig
    from .llm_functions import get_relevant_class_resource_chunks
    from ..databases.document_db_schemas import ClassResourceChunkDocument
    from .llm_schemas import (
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        ValidatedFormatString,
    )
except (KeyError, ImportError):
    from taibackend.shared_schemas import BaseOpenAIConfig
    from taibackend.taitutors.llm_functions import get_relevant_class_resource_chunks
    from taibackend.taitutors.llm_schemas import (
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        ValidatedFormatString,
    )


class ModelName(str, Enum):
    """Define the supported LLMs."""
    GPT_TURBO = "gpt-3.5-turbo"
    GPT_TURBO_LARGE_CONTEXT = "gpt-3.5-turbo-16k"
    GPT_4 = "gpt-4"


class ChatOpenAIConfig(BaseOpenAIConfig):
    """Define the config for the chat openai model."""
    model_name: ModelName = Field(
        default=ModelName.GPT_TURBO,
        description="The name of the model to use.",
    )
    stream_response: bool = Field(
        default=False,
        description="Whether or not to stream the response.",
    )

    class Config:
        """Define the pydantic config."""
        use_enum_values = True


class TaiLLM:
    """Define the interface for connecting to LLMs."""
    def __init__(self, config: ChatOpenAIConfig):
        """Initialize the LLMs interface."""
        self._config = config
        self._chat_model: BaseChatModel = ChatOpenAI(
            openai_api_key=config.api_key,
            request_timeout=config.request_timeout,
            model=config.model_name,
            streaming=config.stream_response,
        )

    def add_tai_tutor_chat_response(
        self,
        chat_session: TaiChatSession,
        relevant_chunks: Optional[list[ClassResourceChunkDocument]] = None,
    ) -> None:
        """Get the response from the LLMs."""
        llm_kwargs ={}
        if relevant_chunks:
            self._append_synthetic_function_call_to_chat(
                chat_session,
                function_to_call=get_relevant_class_resource_chunks,
                function_kwargs={'student_message': chat_session.last_student_message.content},
                relevant_chunks=relevant_chunks,
            )
            chain = create_openai_fn_chain(
                functions=[get_relevant_class_resource_chunks],
                llm=self._chat_model,
                prompt=PromptTemplate(input_variables=[], template=""),
            )
            llm_kwargs = chain.llm_kwargs
            llm_kwargs['function_call'] = "none"
        self._append_model_response(chat_session, chunks=relevant_chunks)

    def create_search_result_summary_snippet(self, search_query: str, chunks: list[ClassResourceChunkDocument]) -> str:
        """Create a snippet of the search result summary."""
        documents = "\n".join([chunk.simplified_string for chunk in chunks])
        format_str = ValidatedFormatString(
            format_string=SUMMARIZER_USER_PROMPT,
            kwargs={"search_query": search_query, "documents": documents},
        )
        session: TaiChatSession = TaiChatSession.from_message(
            SearchQuery(content=format_str.format()),
            class_id=uuid4(),
        )
        session.insert_system_prompt(SUMMARIZER_SYSTEM_PROMPT)
        self.add_tai_tutor_chat_response(session)
        return session.last_chat_message.content

    def _append_model_response(self, chat_session: TaiChatSession, chunks: list[ClassResourceChunkDocument] = None) -> None:
        """Get the response from the LLMs."""
        chat_message = self._chat_model(messages=chat_session.messages)
        tutor_response = TaiTutorMessage(
            content=chat_message.content,
            render_chat=True,
            class_resource_chunks=chunks if chunks else [],
            **chat_session.last_human_message.dict(exclude={"role", "render_chat", "content"}),
        )
        chat_session.append_chat_messages([tutor_response])

    def _append_synthetic_function_call_to_chat(
        self,
        chat_session: TaiChatSession,
        function_to_call: callable,
        function_kwargs: dict,
        relevant_chunks: list[ClassResourceChunkDocument] = None,
    ) -> None:
        """Append the context chat to the chat session."""
        last_student_chat = chat_session.last_student_message
        tutor_chat = TaiTutorMessage(
            render_chat=False,
            content="",
            function_call=AIResponseCallingFunction(
                name=function_to_call.__name__,
                arguments=json.dumps(function_kwargs),
            ),
            tai_tutor_name=last_student_chat.tai_tutor_name,
        )
        func_message = self._function_msg_from_chunks(relevant_chunks)
        chat_session.append_chat_messages([tutor_chat, func_message])

    def _function_msg_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> FunctionMessage:
        """Create a function message from the chunks."""
        msg = FunctionMessage(
            name="find_relevant_chunks",
            render_chat=False,
            content="\n".join([chunk.simplified_string for chunk in chunks]),
        )
        return msg
