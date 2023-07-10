"""Define the llms interface used for the TAI chat backend."""
from enum import Enum
import json
from typing import Optional
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
        FunctionMessage,
        AIResponseCallingFunction,
    )
except (KeyError, ImportError):
    from taibackend.shared_schemas import BaseOpenAIConfig
    from taibackend.taitutors.llm_functions import get_relevant_class_resource_chunks
    from taibackend.taitutors.llm_schemas import (
        TaiChatSession,
        TaiTutorMessage,
        FunctionMessage,
        AIResponseCallingFunction,
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
            self._append_context_chat(chat_session, relevant_chunks)
            chain = create_openai_fn_chain(
                functions=[get_relevant_class_resource_chunks],
                llm=self._chat_model,
                prompt=PromptTemplate(input_variables=[], template=""),
            )
            llm_kwargs = chain.llm_kwargs
            llm_kwargs['function_call'] = "none"
        chat_message = self._chat_model(messages=chat_session.messages, **llm_kwargs)
        tutor_response = TaiTutorMessage(
            content=chat_message.content,
            render_chat=True,
            **chat_session.last_chat_message.dict(exclude={"role", "render_chat", "content"}),
        )
        chat_session.append_chat_messages([tutor_response])

    def _append_context_chat(
        self,
        chat_session: TaiChatSession,
        relevant_chunks: list[ClassResourceChunkDocument] = None,
    ) -> None:
        """Append the context chat to the chat session."""
        last_chat = chat_session.last_chat_message
        tutor_chat = TaiTutorMessage(
            render_chat=False,
            content="",
            function_call=AIResponseCallingFunction(
                name="find_relevant_chunks",
                arguments=json.dumps({'student_message': last_chat.content}),
            ),
            tai_tutor_name=last_chat.tai_tutor_name,
        )
        function_response = ""
        for chunk in relevant_chunks:
            function_response += f"{chunk.dict(serialize_dates=True)}\n\n"
        func_message = FunctionMessage(
            name="find_relevant_chunks",
            render_chat=False,
            content=function_response,
            **chat_session.last_chat_message.dict(exclude={"role", "render_chat", "content"}),
        )
        chat_session.append_chat_messages([tutor_chat, func_message])
