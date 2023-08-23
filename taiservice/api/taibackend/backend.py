"""Define the class resources backend."""
import json
import traceback
from collections import deque
from datetime import datetime, date, timedelta
from uuid import UUID
from typing import Literal, Union, Any, Optional
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
    )
    from ..runtime_settings import TaiApiSettings
    from ..routers.class_resources_schema import (
        ClassResource,
        ClassResources,
        FailedResources,
        ResourceUploadFailureReason,
        FailedResource,
    )
    from ..routers.tai_schemas import (
        BaseChatSession as APIChatSession,
        Chat as APIChat,
        StudentChat as APIStudentChat,
        TaiTutorChat as APITaiTutorChat,
        FunctionChat as APIFunctionChat,
        ResourceSearchQuery,
        SearchQuery,
        SearchResults,
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
    )
    from runtime_settings import TaiApiSettings
    from routers.common_resources_schema import (
        CommonQuestion as APICommonQuestion,
        CommonQuestions as APICommonQuestions,
        FrequentlyAccessedResources as APIFrequentlyAccessedResources,
        DateRange as APIDateRange,
    )
    from routers.class_resources_schema import (
        ClassResource,
        ClassResources,
        FailedResources,
        ResourceUploadFailureReason,
        FailedResource,
    )
    from routers.tai_schemas import (
        BaseChatSession as APIChatSession,
        Chat as APIChat,
        StudentChat as APIStudentChat,
        TaiTutorChat as APITaiTutorChat,
        FunctionChat as APIFunctionChat,
        ResourceSearchQuery,
        SearchQuery,
        SearchResults,
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
            messages=converted_chats,
            **chat_session.dict(exclude={"chats"}),
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
            chats=converted_chats,
            **chat_session.dict(exclude={"messages"}),
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

    # TODO: Add a test to verify the archive method is called
    def get_tai_response(self, chat_session: APIChatSession, stream: bool=False) -> APIChatSession:
        """Get and add the tai tutor response to the chat session."""
        chat_session: BEChatSession = self.to_backend_chat_session(chat_session)
        self._archive_message(chat_session.last_human_message, chat_session.class_id)
        search_query = SearchQuery(
            id=chat_session.id,
            class_id=chat_session.class_id,
            query=chat_session.last_student_message.content,
        )
        search_results = self._get_search_results(search_query, "tutor-search")
        tai_llm = TaiLLM(self._get_tai_llm_config(stream))
        tai_llm.add_tai_tutor_chat_response(chat_session, search_results.suggested_resources)
        return self.to_api_chat_session(chat_session)

    # TODO: Add a test to verify the archive method is called
    # TODO: need to refactor this so it doesn't use the api layer sshema
    def search(self, query: ResourceSearchQuery, result_type: Literal['summary', 'results']) -> Union[SearchResults, str]:
        """Search for class resources."""
        student_message = BEStudentMessage(content=query.query)
        self._archive_message(student_message, query.class_id)
        search_query = SearchQuery(
            id=query.id,
            class_id=query.class_id,
            query=query.query,
        )
        search_results = self._get_search_results(search_query, "search-engine")
        if search_results and result_type == 'summary':
            tai_llm = TaiLLM(self._get_tai_llm_config())
            snippet = tai_llm.create_search_result_summary_snippet(
                user_id=search_query.user_id,
                search_query=search_query.query,
                chunks=search_results.suggested_resources
            )
            return snippet
        return search_results

    def create_class_resources(self, class_resources: ClassResources) -> FailedResources:
        """Create a list of class resources."""
        url = f"{self._runtime_settings.search_service_api_url}/class-resources"
        failed_resources = FailedResources()
        resource_queue = deque(class_resources.class_resources)
        while resource_queue:
            resource = resource_queue.popleft()
            try:
                response = requests.post(url, data=resource.json(), timeout=15)
            except Exception as e: # pylint: disable=broad-except
                logger.error(f"Failed to create class resource. Exception: {e}")
                failed_resources = FailedResources()
                for resource in resource_queue:
                    failed_resources.failed_resources.append(
                        FailedResource(
                            failure_reason=ResourceUploadFailureReason.UNPROCESSABLE_RESOURCE,
                            message="Failed to create class resource.",
                            **resource.dict(),
                        )
                    )
            if response.status_code not in {200, 201, 202}:
                if response.status_code == 409:
                    reason = ResourceUploadFailureReason.DUPLICATE_RESOURCE
                elif response.status_code == 429:
                    reason = ResourceUploadFailureReason.TO_MANY_REQUESTS
                else:
                    reason = ResourceUploadFailureReason.UNPROCESSABLE_RESOURCE
                error_message = response.json().get('message', "Failed to create class resource.")
                logger.error(error_message)
                failed_resources.failed_resources.append(
                    FailedResource(
                        failure_reason=reason,
                        message=error_message,
                        **resource.dict(),
                    )
                )
        return failed_resources


    def get_class_resources(self, ids: list[UUID], from_class_ids: bool = False) -> list[ClassResource]:
        """Get the class resources."""
        url = f"{self._runtime_settings.search_service_api_url}/class-resources"
        logger.info(f"Getting class resources from {url}")
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
                return class_resources
            except Exception as e: # pylint: disable=broad-except
                error_message = f"Failed to parse class resources. Exception: {e}"
        else:
            error_message = f"Failed to retrieve class resources. Status code: {response.status_code}"
        raise RuntimeError(error_message)

    def get_frequently_accessed_class_resources(
        self,
        class_id: UUID,
    ) -> APIFrequentlyAccessedResources:
        """Get the most frequently accessed class resources from the tai search service."""
        url = f"{self._runtime_settings.search_service_api_url}/frequently-accessed-resources/{class_id}"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            try:
                data = response.json()
                return APIFrequentlyAccessedResources(**data)
            except Exception as e: # pylint: disable=broad-except
                error_message = f"Failed to parse frequently accessed resources. Exception: {e}"
        else:
            error_message = f"Failed to retrieve frequently accessed resources. Status code: {response.status_code}"
        logger.critical(error_message)
        raise RuntimeError(error_message)

    def update_class_resources(self, class_resources: list[ClassResource]) -> None:
        """Update a list of class resources."""
        pass #TODO call new tai search service

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete a list of class resources."""
        pass #TODO call new tai search service

    def _get_search_results(self, query: SearchQuery, endpoint_name: str) -> SearchResults:
        url = f"{self._runtime_settings.search_service_api_url}/{endpoint_name}"
        response = requests.post(url, data=query.json(), timeout=15)
        logger.info(f"Search response status code: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                return SearchResults(**data)
            except Exception as e: # pylint: disable=broad-except
                raise RuntimeError(f"Failed to parse class resources. Exception: {e}")
        raise RuntimeError(f"Failed to retrieve class resources. Status code: {response.status_code}")

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
