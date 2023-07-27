"""Define the llms interface used for the TAI chat backend."""
import traceback
from uuid import UUID
from uuid import uuid4
from enum import Enum
import json
from typing import Any, Dict, Optional, Union
from langchain.chat_models import ChatOpenAI
from langchain import PromptTemplate
from langchain.chat_models.base import BaseChatModel
from langchain.chains.openai_functions.base import create_openai_fn_chain
from loguru import logger
from pydantic import Field
# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import BaseOpenAIConfig
    from .llm_functions import (
        get_relevant_class_resource_chunks,
        save_student_conversation_topics,
        save_student_questions,
    )
    from ..databases.document_db_schemas import ClassResourceChunkDocument
    from ..databases.archiver import Archive
    from .llm_schemas import (
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT,
        HARD_CODED_CLASS_NAME,
        STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT,
        FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
        STEERING_PROMPT,
        ValidatedFormatString,
    )
except (KeyError, ImportError):
    from taibackend.shared_schemas import BaseOpenAIConfig
    from taibackend.taitutors.llm_functions import (
        get_relevant_class_resource_chunks,
        save_student_conversation_topics,
        save_student_questions,
    )
    from taibackend.databases.document_db_schemas import ClassResourceChunkDocument
    from taibackend.databases.archiver import Archive
    from taibackend.taitutors.llm_schemas import (
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT,
        HARD_CODED_CLASS_NAME,
        STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT,
        FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
        STEERING_PROMPT,
        ValidatedFormatString,
    )


class ModelName(str, Enum):
    """Define the supported LLMs."""
    GPT_TURBO = "gpt-3.5-turbo"
    GPT_TURBO_LARGE_CONTEXT = "gpt-3.5-turbo-16k"
    GPT_4 = "gpt-4"


class ChatOpenAIConfig(BaseOpenAIConfig):
    """Define the config for the chat openai model."""
    basic_model_name: ModelName = Field(
        default=ModelName.GPT_TURBO,
        description="The name of the model to use for the llm tutor for basic queries.",
    )
    large_context_model_name: ModelName = Field(
        default=ModelName.GPT_TURBO_LARGE_CONTEXT,
        description="The name of the model to use for the llm tutor for large context queries.",
    )
    advanced_model_name: ModelName = Field(
        default=ModelName.GPT_4,
        description="The name of the model to use for the llm tutor for advanced queries.",
    )
    stream_response: bool = Field(
        default=False,
        description="Whether or not to stream the response.",
    )
    message_archive: Archive = Field(
        ...,
        description="The archive to use for archiving messages.",
    )
    class_name: str = Field(
        default=HARD_CODED_CLASS_NAME,
        description="The name of the class.",
    )

    class Config:
        """Define the pydantic config."""
        use_enum_values = True
        arbitrary_types_allowed = True


class TaiLLM:
    """Define the interface for connecting to LLMs."""
    def __init__(self, config: ChatOpenAIConfig):
        """Initialize the LLMs interface."""
        self._config = config
        base_config = {
            "openai_api_key": config.api_key,
            "streaming": config.stream_response,
        }
        self.basic_chat_model: BaseChatModel = ChatOpenAI(
            model=config.basic_model_name,
            request_timeout=config.request_timeout,
            **base_config,
        )
        self.large_context_chat_model: BaseChatModel = ChatOpenAI(
            model=config.large_context_model_name,
            request_timeout=config.request_timeout + 15,
            **base_config,
        )
        self.advanced_chat_model: BaseChatModel = ChatOpenAI(
            model=config.advanced_model_name,
            request_timeout=config.request_timeout + 30,
            **base_config,
        )
        self._archive = config.message_archive
        self._class_name = config.class_name

    def add_tai_tutor_chat_response(
        self,
        chat_session: TaiChatSession,
        relevant_chunks: Optional[list[ClassResourceChunkDocument]] = None,
        function_to_call: Optional[callable] = None,
        functions: Optional[list[callable]] = None,
        ModelToUse: Optional[BaseChatModel] = None,
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
        if relevant_chunks is not None and len(relevant_chunks) == 0:
            format_str = ValidatedFormatString(
                format_string=STEERING_PROMPT,
                kwargs={"class_name": self._class_name},
            )
            chat_session.append_chat_messages([TaiTutorMessage(
                content=format_str.format(),
                render_chat=False,
            )])
        if function_to_call:
            assert functions, "Must provide functions if function_to_call is provided."
            chain = create_openai_fn_chain(
                functions=[function_to_call],
                llm=self.large_context_chat_model,
                prompt=PromptTemplate(input_variables=[], template=""),
            )
            llm_kwargs = chain.llm_kwargs
        # function_to_call = {'name': function_to_call.__name__} if function_to_call else "none"
        # llm_kwargs['function_call'] = function_to_call
        # langchain does the above line for us, but it's left here for reference
        self._append_model_response(chat_session, chunks=relevant_chunks, ModelToUse=ModelToUse, **llm_kwargs)

    def create_search_result_summary_snippet(
        self,
        class_id: UUID,
        search_query: str,
        chunks: list[ClassResourceChunkDocument]
    ) -> str:
        """Create a snippet of the search result summary."""
        session: TaiChatSession = TaiChatSession.from_message(
            SearchQuery(content=search_query),
            class_id=class_id,
        )
        documents = "\n".join([chunk.simplified_string for chunk in chunks])
        format_str = ValidatedFormatString(
            format_string=SUMMARIZER_USER_PROMPT,
            kwargs={"documents": documents, "user_query": search_query},
        )
        session.append_chat_messages([FunctionMessage(
            content=format_str.format(),
            name="get_search_results_for_query",
        )])
        session.insert_system_prompt(SUMMARIZER_SYSTEM_PROMPT)
        self.add_tai_tutor_chat_response(session)
        return session.last_chat_message.content

    def summarize_student_messages(self, messages: list[str], as_questions: bool = False) -> list[str]:
        """Summarize the student messages."""
        def get_summaries(messages: list[str], system_prompt: str, function: callable, ModelToUse: BaseChatModel = None) -> list[str]:
            session: TaiChatSession = TaiChatSession.from_message(
                SearchQuery(content="\n".join(messages)),
                class_id=uuid4(),
            )
            session.insert_system_prompt(system_prompt)
            self.add_tai_tutor_chat_response(
                session,
                function_to_call=function,
                functions=[function],
                ModelToUse=ModelToUse,
            )
            last_chat: TaiTutorMessage = session.last_chat_message
            args = last_chat.function_call.arguments
            # there should only be one argument, so we can just return the first one
            return list(args.values())[0]
        if as_questions:
            function = save_student_questions
            system_prompt = STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT
        else:
            function = save_student_conversation_topics
            system_prompt = STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT
        summaries = get_summaries(
            messages,
            system_prompt,
            function,
            ModelToUse=self.large_context_chat_model
        )
        if not as_questions:
            summaries = get_summaries(
                "\n".join(summaries),
                FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
                function,
                ModelToUse=self.advanced_chat_model
            )
        return summaries

    def _append_model_response(
        self,
        chat_session: TaiChatSession,
        chunks: list[ClassResourceChunkDocument] = None,
        ModelToUse: Optional[BaseChatModel] = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        """Get the response from the LLMs."""
        if not ModelToUse:
            ModelToUse = self.basic_chat_model
        chat_message = ModelToUse(messages=chat_session.messages, **kwargs)
        function_call: dict = chat_message.additional_kwargs.get("function_call")
        if function_call:
            function_call = AIResponseCallingFunction(
                name=function_call.get("name"),
                arguments=json.loads(function_call.get("arguments")),
            )
        tutor_response = TaiTutorMessage(
            content=chat_message.content,
            render_chat=True,
            class_resource_chunks=chunks if chunks else [],
            function_call=function_call,
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
                arguments=function_kwargs,
            ),
            tai_tutor_name=last_student_chat.tai_tutor_name,
        )
        func_message = self._function_msg_from_chunks(relevant_chunks)
        chat_session.append_chat_messages([tutor_chat, func_message])

    def _function_msg_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> FunctionMessage:
        """Create a function message from the chunks."""
        chunks = "\n".join([chunk.simplified_string for chunk in chunks])
        msg = FunctionMessage(
            name="find_relevant_chunks",
            render_chat=False,
            content=chunks,
        )
        return msg
