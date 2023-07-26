"""Define the class resources backend."""
import json
import traceback
from datetime import datetime, date, timedelta
from uuid import UUID, uuid4
from typing import Union, Any, Optional
from loguru import logger
import boto3
from botocore.exceptions import ClientError
try:
    from .errors import DuplicateClassResourceError
    from .databases.archiver import Archive
    from .metrics import (
        Metrics,
        MetricsConfig,
        DateRange as BEDateRange,
    )
    from ..routers.common_resources_schema import (
        FrequentlyAccessedResources as APIFrequentlyAccessedResources,
        FrequentlyAccessedResource as APIFrequentlyAccessedResource,
        CommonQuestions as APICommonQuestions,
        CommonQuestion as APICommonQuestion,
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
    from ..routers.class_resources_schema import (
        ClassResource,
        BaseClassResource,
        ClassResourceProcessingStatus,
        Metadata as APIResourceMetadata,
    )
    from ..routers.tai_schemas import (
        ClassResourceSnippet,
        BaseChatSession as APIChatSession,
        Chat as APIChat,
        StudentChat as APIStudentChat,
        TaiTutorChat as APITaiTutorChat,
        FunctionChat as APIFunctionChat,
        ResourceSearchQuery,
        ResourceSearchAnswer,
    )
    from .databases.document_db_schemas import (
        ClassResourceDocument,
        ClassResourceChunkDocument,
        ChunkMetadata,
    )
    from .shared_schemas import (
        Metadata as DBResourceMetadata,
        ClassResourceType as DBResourceType,
        BaseClassResourceDocument,
    )
    from .databases.document_db import DocumentDB, DocumentDBConfig
    from .databases.pinecone_db import PineconeDB, PineconeDBConfig
    from .indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        OpenAIConfig,
        IngestedDocument,
    )
except (KeyError, ImportError):
    from taibackend.databases.archiver import Archive
    from taibackend.metrics import (
        Metrics,
        MetricsConfig,
        DateRange as BEDateRange,
    )
    from taibackend.errors import DuplicateClassResourceError
    from routers.common_resources_schema import (
        FrequentlyAccessedResources as APIFrequentlyAccessedResources,
        FrequentlyAccessedResource as APIFrequentlyAccessedResource,
        CommonQuestions as APICommonQuestions,
        CommonQuestion as APICommonQuestion,
        DateRange as APIDateRange,
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
    from taibackend.databases.document_db_schemas import (
        ClassResourceDocument,
        ClassResourceChunkDocument,
        ChunkMetadata,
    )
    from taibackend.shared_schemas import (
        Metadata as DBResourceMetadata,
        ClassResourceType as DBResourceType,
        BaseClassResourceDocument,
    )
    from taibackend.databases.document_db import DocumentDB, DocumentDBConfig
    from taibackend.databases.pinecone_db import PineconeDB, PineconeDBConfig
    from taibackend.indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        OpenAIConfig,
        IngestedDocument,
    )
    from runtime_settings import TaiApiSettings
    from routers.class_resources_schema import (
        ClassResource,
        BaseClassResource,
        ClassResourceProcessingStatus,
        Metadata as APIResourceMetadata,
    )
    from routers.tai_schemas import (
        ClassResourceSnippet,
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
        pinecone_api_key = self._get_secret_value(runtime_settings.pinecone_db_api_key_secret_name)
        self._pinecone_db_config = PineconeDBConfig(
            api_key=pinecone_api_key,
            environment=runtime_settings.pinecone_db_environment,
            index_name=runtime_settings.pinecone_db_index_name,
        )
        self._pinecone_db = PineconeDB(self._pinecone_db_config)
        db_credentials = self._get_secret_value(runtime_settings.doc_db_credentials_secret_name)
        self._doc_db_config = DocumentDBConfig(
            username=db_credentials[runtime_settings.doc_db_username_secret_key],
            password=db_credentials[runtime_settings.doc_db_password_secret_key],
            fully_qualified_domain_name=runtime_settings.doc_db_fully_qualified_domain_name,
            port=runtime_settings.doc_db_port,
            database_name=runtime_settings.doc_db_database_name,
            class_resource_collection_name=runtime_settings.doc_db_class_resource_collection_name,
            class_resource_chunk_collection_name=runtime_settings.doc_db_class_resource_chunk_collection_name,
        )
        self._doc_db = DocumentDB(self._doc_db_config)
        self._openai_api_key = self._get_secret_value(runtime_settings.openAI_api_key_secret_name)
        openAI_config = OpenAIConfig(
            api_key=self._openai_api_key,
            batch_size=runtime_settings.openAI_batch_size,
            request_timeout=runtime_settings.base_openAI_request_timeout,
        )
        self._indexer_config = IndexerConfig(
            pinecone_db_config=self._pinecone_db_config,
            document_db_config=self._doc_db_config,
            openai_config=openAI_config,
            cold_store_bucket_name=runtime_settings.cold_store_bucket_name,
            chrome_driver_path=runtime_settings.chrome_driver_path,
        )
        self._indexer = Indexer(self._indexer_config)
        self._llm_message_archive = Archive(runtime_settings.message_archive_bucket_name)
        self._metrics = Metrics(
            MetricsConfig(
                document_db_instance=self._doc_db,
                openai_config=self._get_tai_llm_config(),
                pinecone_db_instance=self._pinecone_db,
                archive=self._llm_message_archive,
            )
        )

    @staticmethod
    def to_api_resources(
        documents: Union[list[BaseClassResourceDocument], BaseClassResourceDocument],
    ) -> Union[list[BaseClassResource], BaseClassResource]:
        """Convert the database documents to API documents."""
        input_was_list = isinstance(documents, list)
        if isinstance(documents, BaseClassResourceDocument):
            documents = [documents]
            input_was_list = False
        output_documents = []
        for doc in documents:
            metadata = doc.metadata
            base_doc = BaseClassResource(
                id=doc.id,
                class_id=doc.class_id,
                full_resource_url=doc.full_resource_url,
                preview_image_url=doc.preview_image_url,
                metadata=APIResourceMetadata(
                    title=metadata.title,
                    description=metadata.description,
                    tags=metadata.tags,
                    resource_type=metadata.resource_type,
                ),
            ).dict()
            if isinstance(doc, ClassResourceDocument):
                output_doc = ClassResource(status=doc.status, **base_doc)
            elif isinstance(doc, ClassResourceChunkDocument):
                output_doc = ClassResourceSnippet(resource_snippet=doc.chunk, raw_snippet_url=doc.raw_chunk_url, **base_doc)
            else:
                raise RuntimeError(f"Unknown document type: {doc}")
            output_documents.append(output_doc)
        return output_documents if input_was_list else output_documents[0]

    @staticmethod
    def to_backend_resources(documents: list[BaseClassResource]) -> list[BaseClassResourceDocument]:
        """Convert the API documents to database documents."""
        output_documents = []
        for doc in documents:
            metadata = doc.metadata
            base_doc = BaseClassResourceDocument(
                id=doc.id,
                class_id=doc.class_id,
                full_resource_url=doc.full_resource_url,
                preview_image_url=doc.preview_image_url,
                metadata=DBResourceMetadata(
                    title=metadata.title,
                    description=metadata.description,
                    tags=metadata.tags,
                    resource_type=metadata.resource_type,
                ),
            )
            if isinstance(doc, ClassResource):
                output_doc = ClassResourceDocument(status=doc.status, **base_doc.dict())
            elif isinstance(doc, ClassResourceSnippet):
                base_doc.metadata = ChunkMetadata(
                    class_id=doc.class_id,
                    **base_doc.metadata.dict(),
                )
                output_doc = ClassResourceChunkDocument(
                    chunk=doc.resource_snippet,
                    raw_chunk_url=doc.raw_snippet_url,
                    **base_doc.dict()
                )
            else:
                raise RuntimeError(f"Unknown document type: {doc}")
            output_documents.append(output_doc)
        return output_documents

    @staticmethod
    def to_backend_input_docs(resources: list[ClassResource]) -> list[InputDocument]:
        """Convert the API documents to database documents."""
        input_documents = []
        for resource in resources:
            metadata = resource.metadata
            input_doc = InputDocument(
                id=resource.id,
                class_id=resource.class_id,
                full_resource_url=resource.full_resource_url,
                preview_image_url=resource.preview_image_url,
                status=resource.status,
                metadata=DBResourceMetadata(
                    title=metadata.title,
                    description=metadata.description,
                    tags=metadata.tags,
                    resource_type=metadata.resource_type,
                )
            )
            input_documents.append(input_doc)
        return input_documents

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
            chunks = cls.to_backend_resources(chat_message.class_resource_snippets)
            return BETaiTutorMessage(
                render_chat=chat_message.render_chat,
                tai_tutor_name=chat_message.tai_tutor,
                technical_level=chat_message.technical_level,
                class_resource_chunks=[chunk for chunk in chunks if isinstance(chunk, ClassResourceChunkDocument)],
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
            snippets = cls.to_api_resources(chat_message.class_resource_chunks)
            return APITaiTutorChat(
                render_chat=chat_message.render_chat,
                tai_tutor=chat_message.tai_tutor_name,
                technical_level=chat_message.technical_level,
                class_resource_snippets=[snippet for snippet in snippets if isinstance(snippet, ClassResourceSnippet)],
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

    def get_frequently_accessed_class_resources(
        self,
        class_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> APIFrequentlyAccessedResources:
        """Get the most frequently accessed class resources."""
        date_range = self._get_BE_date_range(start_date, end_date)
        frequent_resources = self._metrics.get_most_frequently_accessed_resources(class_id, date_range)
        ranked_resources: list[APIFrequentlyAccessedResource] = []
        for ranked_resource in frequent_resources.resources:
            ranked_resources.append(
                APIFrequentlyAccessedResource(
                    appearances_during_period=ranked_resource.appearances_during_period,
                    rank=ranked_resource.rank,
                    resource=self.to_api_resources(ranked_resource.resource),
                )
            )
        resources = APIFrequentlyAccessedResources(
            class_id=frequent_resources.class_id,
            date_range=APIDateRange(start_date=frequent_resources.date_range.start_date, end_date=frequent_resources.date_range.end_date),
            resources=[resource.dict() for resource in ranked_resources],
        )
        return resources

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
        chunks = self.get_relevant_class_resources(chat_session.last_chat_message.content, chat_session.class_id)
        tai_llm = TaiLLM(self._get_tai_llm_config(stream))
        student_msg = chat_session.last_student_message
        prompt = BETaiProfile.get_system_prompt(name=student_msg.tai_tutor_name, technical_level=student_msg.technical_level)
        chat_session.insert_system_prompt(prompt)
        tai_llm.add_tai_tutor_chat_response(chat_session, chunks)
        chat_session.remove_system_prompt()
        logger.info(chat_session.dict())
        return self.to_api_chat_session(chat_session)

    # TODO: Add a test to verify the archive method is called
    def search(self, query: ResourceSearchQuery) -> ResourceSearchAnswer:
        """Search for class resources."""
        student_message = BEStudentMessage(content=query.query)
        self._archive_message(student_message, query.class_id)
        chunks = self.get_relevant_class_resources(query.query, query.class_id)
        snippet = ""
        if chunks:
            tai_llm = TaiLLM(self._get_tai_llm_config())
            snippet = tai_llm.create_search_result_summary_snippet(query.class_id, query.query, chunks)
        search_answer = ResourceSearchAnswer(
            summary_snippet=snippet,
            suggested_resources=self.to_api_resources(chunks),
            other_resources=[],
            **query.dict(),
        )
        return search_answer

    def get_relevant_class_resources(self, query: str, class_id: UUID) -> list[ClassResourceChunkDocument]:
        """Get the most relevant class resources."""
        logger.info(f"Getting relevant class resources for query: {query}")
        chunk_doc = ClassResourceChunkDocument(
            class_id=class_id,
            chunk=query,
            full_resource_url="https://www.google.com", # this is a dummy link as it's not needed for the query
            id=uuid4(),
            metadata=DBResourceMetadata(
                class_id=class_id,
                title="User Query",
                description="User Query",
                resource_type=DBResourceType.TEXTBOOK,
            )
        )
        pinecone_docs = self._indexer.embed_documents(documents=[chunk_doc], class_id=class_id)
        similar_docs = self._pinecone_db.get_similar_documents(document=pinecone_docs.documents[0], alpha=0.7)
        uuids = [doc.metadata.chunk_id for doc in similar_docs.documents]
        chunk_docs = self._doc_db.get_class_resources(uuids, ClassResourceChunkDocument, count_towards_metrics=True)
        logger.info(f"Got similar docs: {chunk_docs}")
        return [doc for doc in chunk_docs if isinstance(doc, ClassResourceChunkDocument)]

    def get_class_resources(self, ids: list[UUID], from_class_ids: bool=False) -> list[ClassResource]:
        """Get the class resources."""
        docs = self._doc_db.get_class_resources(ids, ClassResourceDocument, from_class_ids=from_class_ids, count_towards_metrics=False)
        for doc in docs:
            if self._is_stuck_processing(doc.id):
                self._coerce_and_update_status(doc, ClassResourceProcessingStatus.FAILED)
        return self.to_api_resources(docs)

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete the class resources."""
        try:
            docs = self._doc_db.get_class_resources(ids, ClassResourceDocument, count_towards_metrics=False)
            for doc in docs:
                if isinstance(doc, ClassResourceDocument) or isinstance(doc, ClassResourceChunkDocument):
                    if isinstance(doc, ClassResourceDocument):
                        self._coerce_and_update_status(doc, ClassResourceProcessingStatus.DELETING)
                        chunk_docs = self._chunks_from_class_resource(doc)
                    chunk_docs = [doc]
                    self._delete_vectors_from_chunks(chunk_docs)
            failed_docs = self._doc_db.delete_class_resources(docs)
            for doc in failed_docs:
                if isinstance(doc, ClassResourceDocument):
                    self._coerce_and_update_status(doc, ClassResourceProcessingStatus.FAILED)
        except Exception as e:
            logger.critical(f"Failed to delete class resources: {e}")
            raise RuntimeError(f"Failed to delete class resources: {e}") from e

    def create_class_resources(self, class_resources: list[ClassResource]) -> None:
        """Create the class resources."""
        input_docs = self.to_backend_input_docs(class_resources)
        doc_pairs: list[tuple[Indexer, ClassResourceDocument]] = []
        for input_doc in input_docs:
            ingested_doc = self._indexer.ingest_document(input_doc)
            if self._is_stuck_processing(ingested_doc): # if it's stuck, we should continue as the operations are idempotent
                pass
            elif self._is_duplicate_class_resource(ingested_doc):
                raise DuplicateClassResourceError(f"Duplicate class resource: {ingested_doc.id} in class {ingested_doc.class_id}")
            doc = ClassResourceDocument.from_ingested_doc(ingested_doc)
            self._coerce_and_update_status(doc, ClassResourceProcessingStatus.PENDING)
            doc_pairs.append((ingested_doc, doc))
        for ingested_doc, class_resource in doc_pairs:
            try:
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.PROCESSING)
                class_resource = self._indexer.index_resource(ingested_doc, class_resource)
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.COMPLETED)
            except Exception as e: # pylint: disable=broad-except
                logger.critical(f"Failed to create class resources: {e}")
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.FAILED)

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
            request_timeout=self._runtime_settings.base_openAI_request_timeout,
            stream_response=stream,
            basic_model_name=self._runtime_settings.basic_model_name,
            large_context_model_name=self._runtime_settings.large_context_model_name,
            advanced_model_name=self._runtime_settings.advanced_model_name,
            message_archive=self._llm_message_archive,
        )
        return config

    def _coerce_status_to(self, class_resources: list[ClassResourceDocument], status: ClassResourceProcessingStatus) -> None:
        """Coerce the status of the class resources to the given status."""
        for class_resource in class_resources:
            class_resource.status = status

    def _coerce_and_update_status(
        self,
        class_resources: Union[list[ClassResourceDocument], ClassResourceDocument],
        status: ClassResourceProcessingStatus
    ) -> None:
        """Coerce the status of the class resources to the given status and update the database."""
        if isinstance(class_resources, ClassResourceDocument):
            class_resources = [class_resources]
        self._coerce_status_to(class_resources, status)
        self._doc_db.upsert_documents(class_resources)

    def _is_stuck_processing(self, doc_id: UUID) -> bool:
        """Check if the class resource is stuck uploading."""
        class_resource_docs: list[ClassResourceDocument] = self._doc_db.get_class_resources(doc_id, ClassResourceDocument, count_towards_metrics=False)
        doc = class_resource_docs[0] if class_resource_docs else None
        if not doc:
            return False
        stable = doc.status == ClassResourceProcessingStatus.COMPLETED \
            or doc.status == ClassResourceProcessingStatus.FAILED
        if not stable:
            elapsed_time = (datetime.utcnow() - doc.modified_timestamp).total_seconds()
            if elapsed_time > self._runtime_settings.class_resource_processing_timeout:
                return True
        return False

    def _is_duplicate_class_resource(self, doc: IngestedDocument) -> bool:
        """Check if the document can be created."""
        class_resource_docs = self._doc_db.get_class_resources(doc.class_id, ClassResourceDocument, from_class_ids=True, count_towards_metrics=False)
        docs = {doc.id: doc for doc in class_resource_docs}
        doc_hashes = set([class_resource_doc.hashed_document_contents for class_resource_doc in class_resource_docs])
        # find the doc and check the status, if failed, then we can overwrite
        if doc.id in docs and docs[doc.id].status == ClassResourceProcessingStatus.FAILED:
            return False
        return doc.id in docs or doc.hashed_document_contents in doc_hashes

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids, ClassResourceChunkDocument, count_towards_metrics=False)

    def _delete_vectors_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> None:
        """Delete the vectors from the chunks."""
        vector_ids = [chunk.metadata.vector_id for chunk in chunks]
        self._pinecone_db.delete_vectors(vector_ids)

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
