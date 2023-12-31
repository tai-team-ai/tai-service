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
    from .shared_schemas import SearchEngineResponse
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
        ModelName,
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
    from .databases.document_db import (
        DocumentDBConfig,
        DocumentDB,
    )
except (KeyError, ImportError):
    from taibackend.shared_schemas import SearchEngineResponse
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
        ModelName,
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
    from taibackend.databases.document_db import (
        DocumentDBConfig,
        DocumentDB,
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
        db_credentials = self._get_secret_value(runtime_settings.doc_db_credentials_secret_name)
        self._doc_db_config = DocumentDBConfig(
            username=db_credentials[runtime_settings.doc_db_username_secret_key],
            password=db_credentials[runtime_settings.doc_db_password_secret_key],
            fully_qualified_domain_name=runtime_settings.doc_db_fully_qualified_domain_name,
            port=runtime_settings.doc_db_port,
            database_name=runtime_settings.doc_db_database_name,
            class_resource_collection_name=runtime_settings.doc_db_class_resource_collection_name,
        )
        self._doc_db = DocumentDB(self._doc_db_config)

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
                class_resources=chat_message.class_resources,
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
                class_resources=chat_message.class_resources,
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
    def get_tai_response(
        self,
        chat_session: APIChatSession,
        stream: bool = False,
        auto_summarize: bool = True,
    ) -> APIChatSession:
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
        docs_to_use = search_results.long_snippets[:1] + search_results.short_snippets[:2]
        chat_session.remove_unrendered_messages(num_unrendered_blocks_to_keep=1)
        if auto_summarize:
            try:
                self._summarize_chat_session(chat_session, model_name=self._runtime_settings.basic_model_name)
            except: # pylint: disable=bare-except
                logger.error(traceback.format_exc())
        tai_llm.add_tai_tutor_chat_response(chat_session, docs_to_use, model_name=self._runtime_settings.basic_model_name)
        assert isinstance(chat_session.last_chat_message, BETaiTutorMessage)
        chat_session.last_chat_message.class_resources = search_results.class_resources
        return self.to_api_chat_session(chat_session)

    def _summarize_chat_session(self, chat_session: BEChatSession, model_name: ModelName) -> None:
        avg_tokens = chat_session.average_tokens_per_message(exclude_system_prompt=True)
        num_tokens = chat_session.get_token_count(model_name=model_name)
        max_tokens = chat_session.max_tokens_allowed_in_session(model_name=model_name)
        # we want to summarize if we only have approximately 4 messages left
        if avg_tokens * 4 > max_tokens - num_tokens:
            llm = TaiLLM(self._get_tai_llm_config())
            summary = llm.summarize_chat_session(chat_session, model_name=model_name)
            last_student_msg = chat_session.last_student_message
            chat_session.messages = [
                BETaiTutorMessage(
                    content=summary,
                ),
                last_student_msg,
            ]

    # TODO: Add a test to verify the archive method is called
    # TODO: need to refactor this so it doesn't use the api layer sshema
    def search(self, query: ResourceSearchQuery, result_type: Literal['summary', 'results']) -> Union[SearchResults, str]:
        """Search for class resources."""
        student_message = BEStudentMessage(content=query.query)
        self._archive_message(student_message, query.class_id)
        search_results = self._get_search_results(query, "search-engine")
        if search_results and result_type == 'summary':
            docs_to_summarize = search_results.long_snippets[:1] + search_results.short_snippets[:2]
            tai_llm = TaiLLM(self._get_tai_llm_config())
            snippet = tai_llm.create_search_result_summary_snippet(
                user_id=query.user_id,
                search_query=query.query,
                chunks=docs_to_summarize,
            )
            return snippet
        api_search_results = SearchResults(
            suggested_resources=search_results.class_resources[:2],
            other_resources=search_results.class_resources[2:5],
            **search_results.dict(exclude={"short_snippets", "long_snippets"}),
        )
        return api_search_results

    def create_class_resources(self, class_resources: ClassResources) -> FailedResources:
        """Create a list of class resources."""
        url = f"{self._runtime_settings.search_service_api_url}/class-resources"
        failed_resources = FailedResources()

        resource_queue = deque(class_resources.class_resources)
        while resource_queue:
            resource = resource_queue.popleft()
            try:
                response = requests.post(url, data=resource.json(), timeout=40)
                self._check_create_resources_response(response, resource, failed_resources)
            except Exception as e:
                self._handle_create_req_error(e, resource, failed_resources)
        return failed_resources

    def get_class_resources(self, ids: list[UUID], from_class_ids: bool = False) -> list[ClassResource]:
        """Get the class resources."""
        url = f"{self._runtime_settings.search_service_api_url}/class-resources"
        logger.info(f"Getting class resources from {url}")
        params = {
            'ids': ids,
            'from_class_ids': from_class_ids
        }
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537',
            }
            response = requests.get(url, params=params, headers=headers, timeout=7)
            if response.status_code != 200:
                logger.info(f"Failed to retrieve class resources from {url}. Status code: {response.status_code}")
            else:
                try:
                    data = response.json()
                    api_resources = [ClassResource(**item) for item in data['classResources']]
                    return api_resources
                except Exception as e: # pylint: disable=broad-except
                    logger.info(f"Failed to parse class resources from {url}. Exception: {e}")
        except Exception as e: # pylint: disable=broad-except
            logger.warning(f"Failed to retrieve class resources from {url}. Exception: {e}")
            # we fall back to the document db if the search service fails
            resources = self._doc_db.get_class_resources(ids=ids, from_class_ids=from_class_ids)
            api_resources = []
            for resource in resources:
                api_res = ClassResource(
                    id=resource.id,
                    class_id=resource.class_id,
                    full_resource_url=resource.full_resource_url,
                    preview_image_url=resource.preview_image_url,
                    status=resource.status,
                    metadata=resource.metadata,
                )
                api_resources.append(api_res)
            return api_resources

    def get_frequently_accessed_class_resources(
        self,
        class_id: UUID,
    ) -> APIFrequentlyAccessedResources:
        """Get the most frequently accessed class resources from the tai search service."""
        url = f"{self._runtime_settings.search_service_api_url}/frequently-accessed-resources/{class_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537',
        }

        response = requests.get(url, headers=headers, timeout=10)
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

    def _check_create_resources_response(
        self,
        response: requests.Response,
        resource: ClassResource,
        failed_resources: FailedResources
    ) -> None:
        if response.status_code not in {200, 201, 202}:
            if response.status_code == 409:
                reason = ResourceUploadFailureReason.DUPLICATE_RESOURCE
            elif response.status_code == 429:
                reason = ResourceUploadFailureReason.TO_MANY_REQUESTS
            else:
                reason = ResourceUploadFailureReason.UNPROCESSABLE_RESOURCE

            error_message = 'Failed to create class resource.'  # default error message
            
            try:
                response_json = response.json()
                error_message = response_json.get('message', error_message)
            except ValueError:  
                # Catch the ValueError (of which JSONDecodeError is a subclass) and log the response
                error_message = 'Failed to decode response. Raw response: {}'.format(response.text)

            logger.error(error_message)
            self._add_failed_resource(
                failed_resources=failed_resources,
                reason=reason,
                message=error_message,
                resource=resource,
            )

    def _handle_create_req_error(self, e: Exception, resource: ClassResource, failed_resources: FailedResources) -> None:
        logger.error(f"Failed to create class resource with request. Exception: {e}")
        self._add_failed_resource(
            failed_resources=failed_resources,
            reason=ResourceUploadFailureReason.TO_MANY_REQUESTS,
            message="Failed to create class resource with request.",
            resource=resource,
        )

    def _add_failed_resource(
        self,
        failed_resources: FailedResources,
        reason: ResourceUploadFailureReason,
        message: str,
        resource: ClassResource,
    ) -> None:
        failed_resources.failed_resources.append(
            FailedResource(
                failure_reason=reason,
                message=message,
                **resource.dict(),
            )
        )

    def _get_search_results(self, query: SearchQuery, endpoint_name: str) -> SearchEngineResponse:
        url = f"{self._runtime_settings.search_service_api_url}/{endpoint_name}"
        response = requests.post(url, data=query.json(), timeout=15)
        logger.info(f"Search response status code: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                return SearchEngineResponse(**data)
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
