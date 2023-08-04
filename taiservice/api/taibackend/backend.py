"""Define the class resources backend."""
import json
import traceback
from datetime import datetime, date, timedelta
from uuid import UUID
from typing import Union, Any, Optional
import requests
from loguru import logger
import boto3
from botocore.exceptions import ClientError
try:
    from .databases.archiver import Archive
    from .metrics import (
        Metrics,
        MetricsConfig,
        DateRange as BEDateRange,
    )
    from ..routers.common_resources_schema import (
        CommonQuestion as APICommonQuestion,
        CommonQuestions as APICommonQuestions,
        FrequentlyAccessedResources as APIFrequentlyAccessedResources,
        DateRange as APIDateRange,
    )
    from ..taibackend.taitutors.llm import TaiLLM, ChatOpenAIConfig
    from ..taibackend.taitutors.llm_schemas import (
        TaiTutorMessage as BETaiTutorMessage,
        StudentMessage as BEStudentMessage,
        BaseMessage as BEBaseMessage,
        TaiChatSession as BEChatSession,
        FunctionMessage as BEFunctionMessage,
        SystemMessage as BESystemMessage,
        TaiProfile as BETaiProfile,
    )
    from ..runtime_settings import TaiApiSettings
    from ..routers.class_resources_schema import ClassResource
    from ..routers.tai_schemas import (
        BaseChatSession as APIChatSession,
        Chat as APIChat,
        StudentChat as APIStudentChat,
        TaiTutorChat as APITaiTutorChat,
        FunctionChat as APIFunctionChat,
        ResourceSearchQuery,
        ResourceSearchAnswer,
    )
except (KeyError, ImportError):
    from taibackend.databases.archiver import Archive
    from taibackend.metrics import (
        Metrics,
        MetricsConfig,
        DateRange as BEDateRange,
    )
    from taibackend.taitutors.llm import TaiLLM, ChatOpenAIConfig
    from taibackend.taitutors.llm_schemas import (
        TaiTutorMessage as BETaiTutorMessage,
        StudentMessage as BEStudentMessage,
        BaseMessage as BEBaseMessage,
        TaiChatSession as BEChatSession,
        FunctionMessage as BEFunctionMessage,
        SystemMessage as BESystemMessage,
        TaiProfile as BETaiProfile,
    )
    from runtime_settings import TaiApiSettings
    from routers.common_resources_schema import (
        CommonQuestion as APICommonQuestion,
        CommonQuestions as APICommonQuestions,
        FrequentlyAccessedResources as APIFrequentlyAccessedResources,
        DateRange as APIDateRange,
    )
    from routers.class_resources_schema import ClassResource
    from routers.tai_schemas import (
        BaseChatSession as APIChatSession,
        Chat as APIChat,
        StudentChat as APIStudentChat,
        TaiTutorChat as APITaiTutorChat,
        FunctionChat as APIFunctionChat,
        ResourceSearchQuery,
        ResourceSearchAnswer,
    )


class Backend:
    """Class to handle the class resources backend."""
    def __init__(self, runtime_settings: TaiApiSettings) -> None:
        """Initialize the class resources backend."""
        self._runtime_settings = runtime_settings
        self._llm_message_archive = Archive(runtime_settings.message_archive_bucket_name)
        self._openai_api_key = self._get_secret_value(runtime_settings.openAI_api_key_secret_name)
        self._metrics = Metrics(
            MetricsConfig(
                archive=self._llm_message_archive,
                openai_config=self._get_tai_llm_config(),
            )
        )

    @classmethod
    def to_backend_chat_session(cls, chat_session: APIChatSession) -> BEChatSession:
        """Convert the API chat session to a database chat session."""
        converted_chats = []
        for chat in chat_session.chats:
            converted_chats.append(cls.to_backend_chat_message(chat))
        chat_session = BEChatSession(
            id=chat_session.id,
            class_id=chat_session.class_id,
            messages=converted_chats,
        )
        return chat_session

    @classmethod
    def to_backend_chat_message(cls, chat_message: APIChat) -> BEBaseMessage:
        """Convert the API chat message to a database chat message."""
        msg = BEBaseMessage(
            role=chat_message.role,
            content=chat_message.message,
            render_chat=chat_message.render_chat,
        )
        if isinstance(chat_message, APIStudentChat):
            return BEStudentMessage(
                render_chat=chat_message.render_chat,
                tai_tutor_name=chat_message.requested_tai_tutor,
                technical_level=chat_message.requested_technical_level,
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, APITaiTutorChat):
            return BETaiTutorMessage(
                render_chat=chat_message.render_chat,
                tai_tutor_name=chat_message.tai_tutor,
                technical_level=chat_message.technical_level,
                class_resource_snippets=chat_message.class_resource_snippets,
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, APIFunctionChat):
            return BEFunctionMessage(
                name=chat_message.function_name,
                render_chat=chat_message.render_chat,
                **msg.dict(exclude={"render_chat"}),
            )
        else:
            raise RuntimeError(f"Unknown chat message type: {chat_message}")

    @classmethod
    def to_api_chat_session(cls, chat_session: BEChatSession) -> APIChatSession:
        """Convert the database chat session to an API chat session."""
        converted_chats = []
        for chat in chat_session.messages:
            chat = cls.to_api_chat_message(chat)
            if chat:
                converted_chats.append(chat)
        chat_session = APIChatSession(
            id=chat_session.id,
            class_id=chat_session.class_id,
            chats=converted_chats,
        )
        return chat_session

    @classmethod
    def to_api_chat_message(cls, chat_message: BEBaseMessage) -> Optional[APIChat]:
        """Convert the database chat message to an API chat message."""
        msg = APIChat(
            message=chat_message.content,
            role=chat_message.role,
            render_chat=chat_message.render_chat,
        )
        if isinstance(chat_message, BEStudentMessage):
            return APIStudentChat(
                render_chat=chat_message.render_chat,
                requested_tai_tutor=chat_message.tai_tutor_name,
                requested_technical_level=chat_message.technical_level,
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, BETaiTutorMessage):
            return APITaiTutorChat(
                render_chat=chat_message.render_chat,
                tai_tutor=chat_message.tai_tutor_name,
                technical_level=chat_message.technical_level,
                class_resource_snippets=chat_message.class_resource_snippets,
                function_call=chat_message.function_call,
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, BEFunctionMessage):
            return APIFunctionChat(
                function_name=chat_message.name,
                render_chat=chat_message.render_chat,
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, BESystemMessage):
            return
        else:
            raise RuntimeError(f"Unknown chat message type: {chat_message}")

    def get_frequently_asked_questions(
        self,
        class_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> APICommonQuestions:
        """Get the most frequently asked questions."""
        date_range = self._get_BE_date_range(start_date, end_date)
        frequent_questions = self._metrics.get_most_frequently_asked_questions(class_id, date_range)
        api_questions = APICommonQuestions(
            class_id=class_id,
            date_range=APIDateRange(start_date=date_range.start_date, end_date=date_range.end_date),
            common_questions=[],
        )
        if not frequent_questions:
            return api_questions
        for ranked_question in frequent_questions.common_questions:
            api_questions.common_questions.append(
                APICommonQuestion(
                    appearances_during_period=ranked_question.appearances_during_period,
                    rank=ranked_question.rank,
                    question=ranked_question.question,
                )
            )
        return api_questions

    def get_frequently_accessed_class_resources(
        self,
        class_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> APIFrequentlyAccessedResources:
        """Get the most frequently accessed class resources."""
        pass # TODO: call search service


    # TODO: Add a test to verify the archive method is called
    def get_tai_response(self, chat_session: APIChatSession, stream: bool=False) -> APIChatSession:
        """Get and add the tai tutor response to the chat session."""
        chat_session: BEChatSession = self.to_backend_chat_session(chat_session)
        self._archive_message(chat_session.last_human_message, chat_session.class_id)
        # TODO: Call search service to get relevant class resources
        # chunks = self.get_relevant_class_resources(chat_session.last_chat_message.content, chat_session.class_id)
        snippets = []
        tai_llm = TaiLLM(self._get_tai_llm_config(stream))
        student_msg = chat_session.last_student_message
        prompt = BETaiProfile.get_system_prompt(name=student_msg.tai_tutor_name, technical_level=student_msg.technical_level)
        chat_session.insert_system_prompt(prompt)
        tai_llm.add_tai_tutor_chat_response(chat_session, snippets, ModelToUse=tai_llm.large_context_chat_model)
        chat_session.remove_system_prompt()
        logger.info(chat_session.dict())
        return self.to_api_chat_session(chat_session)

    # TODO: Add a test to verify the archive method is called
    def search(self, query: ResourceSearchQuery) -> ResourceSearchAnswer:
        """Search for class resources."""
        student_message = BEStudentMessage(content=query.query)
        self._archive_message(student_message, query.class_id)
        # TODO: Call search service to get relevant class resources
        # snippets = self.get_relevant_class_resources(query.query, query.class_id, is_search=True)
        snippets = []
        snippet = ""
        if snippets:
            tai_llm = TaiLLM(self._get_tai_llm_config())
            snippet = tai_llm.create_search_result_summary_snippet(query.class_id, query.query, snippets)
        search_answer = ResourceSearchAnswer(
            summary_snippet=snippet,
            suggested_resources=snippets,
            other_resources=[],
            **query.dict(),
        )
        return search_answer

    def create_class_resources(self, class_resources: list[ClassResource]) -> None:
        """Create a list of class resources."""
        pass #TODO call new tai search service

    def get_class_resources(self, ids: list[UUID], from_class_ids: bool = False) -> list[ClassResource]:
        """Get the class resources."""
        url = f"{self._runtime_settings.search_service_api_url}/class_resources"
        params = {
            'ids': ids,
            'from_class_ids': from_class_ids
        }
        response = requests.get(url, params=params, timeout=4)
        class_resources = []
        if response.status_code == 200:
            try:
                data = response.json()
                class_resources = [ClassResource(**item) for item in data['classResources']]
            except Exception as e: # pylint: disable=broad-except
                error_message = f"Failed to parse class resources. Exception: {e}"
                logger.error(error_message)
        else:
            error_message = f"Failed to retrieve class resources. Status code: {response.status_code}"
            logger.error(error_message)
        return class_resources

    def update_class_resources(self, class_resources: list[ClassResource]) -> None:
        """Update a list of class resources."""
        pass #TODO call new tai search service

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete a list of class resources."""
        pass #TODO call new tai search service

    def _archive_message(self, message: BEBaseMessage, class_id: UUID) -> None:
        """Archive the message."""
        if message:
            try:
                self._llm_message_archive.archive_message(message, class_id)
            except Exception: # pylint: disable=broad-except
                logger.error(traceback.format_exc())

    def _get_BE_date_range(self, start_date: Optional[date], end_date: Optional[date]) -> BEDateRange:
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.utcnow()
        return BEDateRange(start_date=start_date, end_date=end_date)

    def _get_tai_llm_config(self, stream: bool=False) -> TaiLLM:
        """Initialize the openai api."""
        config = ChatOpenAIConfig(
            api_key=self._openai_api_key,
            request_timeout=self._runtime_settings.openAI_request_timeout,
            stream_response=stream,
            basic_model_name=self._runtime_settings.basic_model_name,
            large_context_model_name=self._runtime_settings.large_context_model_name,
            advanced_model_name=self._runtime_settings.advanced_model_name,
            message_archive=self._llm_message_archive,
        )
        return config

    def _get_secret_value(self, secret_name: str) -> Union[dict[str, Any], str]:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager')
        try:
            get_secret_value_response = client.get_secret_value(
                SecretId=secret_name
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to get secret value: {e}") from e
        secret = get_secret_value_response['SecretString']
        try:
            return json.loads(secret)
        except json.JSONDecodeError:
            return secret
