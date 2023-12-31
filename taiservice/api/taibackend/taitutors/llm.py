"""Define the llms interface used for the TAI chat backend."""
import copy
import json
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID
import tiktoken
from openai.error import InvalidRequestError
from pydantic import BaseModel, Field
from langchain.chat_models import ChatOpenAI
from langchain import PromptTemplate
from langchain.chat_models.base import BaseChatModel
from langchain.chains.openai_functions.base import create_openai_fn_chain
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .errors import UserTokenLimitError, OverContextWindowError
    from .llm_functions import (
        get_relevant_class_resource_chunks,
        save_student_conversation_topics,
        save_student_questions,
    )
    # TODO need to create a separate backend schema for the resources snippet and not use the api def.
    from ...routers.tai_schemas import ClassResourceSnippet
    from ..databases.archiver import Archive
    from .llm_schemas import (
        ModelName,
        BaseLLMChatSession,
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        TaiProfile,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT,
        STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT,
        FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
        STEERING_PROMPT,
        ValidatedFormatString,
    )
    from ..databases.user_data import UserDB, DynamoDB
except (KeyError, ImportError):
    from routers.tai_schemas import ClassResourceSnippet
    from taibackend.taitutors.errors import UserTokenLimitError, OverContextWindowError
    from taibackend.taitutors.llm_functions import (
        get_relevant_class_resource_chunks,
        save_student_conversation_topics,
        save_student_questions,
    )
    from taibackend.databases.archiver import Archive
    from taibackend.taitutors.llm_schemas import (
        ModelName,
        BaseLLMChatSession,
        TaiChatSession,
        TaiTutorMessage,
        SearchQuery,
        TaiProfile,
        FunctionMessage,
        AIResponseCallingFunction,
        SUMMARIZER_SYSTEM_PROMPT,
        SUMMARIZER_USER_PROMPT,
        STUDENT_COMMON_QUESTIONS_SYSTEM_PROMPT,
        STUDENT_COMMON_DISCUSSION_TOPICS_SYSTEM_PROMPT,
        FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
        STEERING_PROMPT,
        ValidatedFormatString,
    )
    from taibackend.databases.user_data import UserDB, DynamoDB


class ChatOpenAIConfig(BaseModel):
    """Define the config for the chat openai model."""
    api_key: str = Field(
        ...,
        description="The openai api key.",
    )
    request_timeout: int = Field(
        default=15,
        description="The number of seconds to wait for a response from the openai api.",
    )
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
    token_reset_interval: timedelta = Field(
        default=timedelta(days=1),
        description="The interval after which the token count of a user is reset.",
    )
    token_limit_per_interval: int = Field(
        default=50000,
        description="The maximum number of tokens per interval.",
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
        self._user_data: UserDB = DynamoDB(
            reset_interval=config.token_reset_interval,
            max_tokens_per_interval=config.token_limit_per_interval,
        )
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
        self._name_to_model_mapping = {
            ModelName.GPT_TURBO: self.basic_chat_model,
            ModelName.GPT_TURBO_LARGE_CONTEXT: self.large_context_chat_model,
            ModelName.GPT_4: self.advanced_chat_model,
        }
        self._archive = config.message_archive

    def add_tai_tutor_chat_response(
        self,
        chat_session: TaiChatSession,
        relevant_chunks: Optional[list[ClassResourceSnippet]] = None,
        return_without_system_prompt: bool = True,
        model_name: ModelName = ModelName.GPT_TURBO,
    ) -> None:
        """Get the response from the LLMs."""
        student_msg = chat_session.last_student_message
        prompt = TaiProfile.get_system_prompt(
            name=student_msg.tai_tutor_name,
            technical_level=student_msg.technical_level,
            class_name=chat_session.class_name,
        )
        chat_session.insert_system_prompt(prompt)
        self._add_tai_tutor_chat_response(
            chat_session,
            relevant_chunks=relevant_chunks,
            model_name=model_name,
        )
        if return_without_system_prompt:
            chat_session.remove_system_prompt()

    def summarize_chat_session(
        self,
        chat_session: BaseLLMChatSession,
        model_name: ModelName = ModelName.GPT_4
    ) -> str:
        """Summarize the chat session"""
        summary = chat_session.summarize(model=self._name_to_model_mapping[model_name])
        return summary

    def create_search_result_summary_snippet(
        self,
        user_id: UUID,
        search_query: str,
        chunks: list[ClassResourceSnippet]
    ) -> str:
        """Create a snippet of the search result summary."""
        if not chunks:
            return ""
        session: BaseLLMChatSession = BaseLLMChatSession.from_message(
            SearchQuery(content=search_query),
            user_id=user_id,
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
        self._append_model_response(session)
        return session.last_chat_message.content

    def summarize_student_messages(self, messages: list[str], as_questions: bool = False) -> list[str]:
        """Summarize the student messages."""
        def get_summaries(messages: list[str], system_prompt: str, function: callable, model_name: ModelName = None) -> list[str]:
            session: BaseLLMChatSession = BaseLLMChatSession.from_message(
                SearchQuery(content="\n".join(messages)),
            )
            session.insert_system_prompt(system_prompt)
            self._add_tai_tutor_chat_response(
                session,
                function_to_call=function,
                functions=[function],
                model_name=model_name,
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
            model_name=ModelName.GPT_TURBO_LARGE_CONTEXT,
        )
        if not as_questions:
            summaries = get_summaries(
                "\n".join(summaries),
                FINAL_STAGE_STUDENT_TOPIC_SUMMARY_SYSTEM_PROMPT,
                function,
                model_name=ModelName.GPT_4,
            )
        return summaries

    def _add_tai_tutor_chat_response(
        self,
        chat_session: TaiChatSession,
        relevant_chunks: Optional[list[ClassResourceSnippet]] = None,
        function_to_call: Optional[callable] = None,
        functions: Optional[list[callable]] = None,
        model_name: Optional[ModelName] = None,
    ) -> None:
        """Get the response from the LLM."""
        llm_kwargs ={}
        if relevant_chunks:
            self._append_synthetic_function_call_to_chat(
                chat_session,
                function_to_call=get_relevant_class_resource_chunks,
                function_kwargs={'student_message': chat_session.last_student_message.content},
                relevant_chunks=relevant_chunks,
            )
            steering_prompt = TaiProfile.get_results_steering_prompt(chat_session.last_student_message.tai_tutor_name)
            chat_session.append_chat_messages([TaiTutorMessage(
                content=steering_prompt,
                render_chat=False,
            )])
        if relevant_chunks is not None and len(relevant_chunks) == 0:
            profile = TaiProfile.get_profile(chat_session.last_student_message.tai_tutor_name)
            format_str = ValidatedFormatString(
                format_string=STEERING_PROMPT,
                kwargs={
                    "class_name": chat_session.class_name,
                    "name": profile.name,
                    "persona": profile.persona,
                },
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
        # IMPORTANT: langchain does the above line for us, but it's left here for reference
        self._append_model_response(chat_session, chunks=relevant_chunks, model_name=model_name, **llm_kwargs)

    def summarize_session(self, chat_session: TaiChatSession) -> None:
        chat_session = copy.deepcopy(chat_session)
        chat_session.remove_unrendered_messages(num_unrendered_blocks_to_keep=2)
        

    def _append_model_response(
        self,
        chat_session: BaseLLMChatSession,
        chunks: Optional[list[ClassResourceSnippet]] = None,
        model_name: Optional[ModelName] = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        """Get the response from the LLMs."""
        if not model_name:
            model_name = ModelName.GPT_TURBO
        chat_model = self._name_to_model_mapping.get(model_name)
        if not chat_model:
            raise ValueError(f"Invalid model name: {model_name}")
        if self._user_data.is_user_over_token_limit(chat_session.user_id):
            raise UserTokenLimitError(chat_session.user_id)
        try:
            chat_message = chat_model(messages=chat_session.messages, **kwargs)
        except InvalidRequestError as e:
            logger.error(e)
            if e.code == "context_length_exceeded":
                raise OverContextWindowError(chat_session.user_id) from e
            raise e
        if chat_session.user_id:
            self._user_data.update_token_count(
                user_id=chat_session.user_id,
                amount=chat_session.get_token_count(model_name=model_name),
            )
        function_call: dict = chat_message.additional_kwargs.get("function_call")
        if function_call:
            function_call = AIResponseCallingFunction(
                name=function_call.get("name"),
                arguments=json.loads(function_call.get("arguments")),
            )
        tutor_response = TaiTutorMessage(
            content=chat_message.content,
            render_chat=True,
            class_resource_snippets=chunks if chunks else [],
            function_call=function_call,
            **chat_session.last_human_message.dict(exclude={"role", "render_chat", "content"}),
        )
        chat_session.append_chat_messages([tutor_response])

    def _append_synthetic_function_call_to_chat(
        self,
        chat_session: TaiChatSession,
        function_to_call: callable,
        function_kwargs: dict,
        relevant_chunks: Optional[list[ClassResourceSnippet]] = None,
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

    def _function_msg_from_chunks(self, chunks: list[ClassResourceSnippet]) -> FunctionMessage:
        """Create a function message from the chunks."""
        chunk_str = "\n\n".join([chunk.simplified_string for chunk in chunks])
        msg = FunctionMessage(
            name="find_relevant_chunks",
            render_chat=False,
            content=chunk_str,
        )
        return msg
