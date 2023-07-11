"""Define the class resources backend."""
import json
from uuid import UUID, uuid4
from typing import Union, Any
from loguru import logger
import boto3
from botocore.exceptions import ClientError
try:
    from ..taibackend.taitutors.llm import TaiLLM, ChatOpenAIConfig
    from ..taibackend.taitutors.llm_schemas import (
        TaiTutorMessage as BETaiTutorMessage,
        StudentMessage as BEStudentMessage,
        BaseMessage as BEBaseMessage,
        TaiChatSession as BEChatSession,
        FunctionMessage as BEFunctionMessage,
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
    )
except (KeyError, ImportError):
    from taibackend.taitutors.llm import TaiLLM, ChatOpenAIConfig
    from taibackend.taitutors.llm_schemas import (
        TaiTutorMessage as BETaiTutorMessage,
        StudentMessage as BEStudentMessage,
        BaseMessage as BEBaseMessage,
        TaiChatSession as BEChatSession,
        FunctionMessage as BEFunctionMessage,
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
            request_timeout=runtime_settings.openAI_request_timeout,
        )
        self._indexer_config = IndexerConfig(
            pinecone_db_config=self._pinecone_db_config,
            document_db_config=self._doc_db_config,
            openai_config=openAI_config,
        )
        self._indexer = Indexer(self._indexer_config)

    def get_tai_tutor_response(self, chat_session: APIChatSession, stream: bool=False) -> APIChatSession:
        """Get and add the tai tutor response to the chat session."""
        config = ChatOpenAIConfig(
            api_key=self._openai_api_key,
            request_timeout=self._runtime_settings.openAI_request_timeout,
            stream_response=stream,
            model_name=self._runtime_settings.model_name,
        )
        tai_llm = TaiLLM(config)
        session = self.to_backend_chat_session(chat_session)
        chunks = self.get_relevant_class_resources(session.last_chat_message.content, session.class_id)
        tai_llm.add_tai_tutor_chat_response(session, chunks)
        return self.to_api_chat_session(session)

    def get_relevant_class_resources(self, query: str, class_id: UUID) -> list[ClassResourceChunkDocument]:
        """Get the most relevant class resources."""
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
        similar_docs = self._pinecone_db.get_similar_documents(document=pinecone_docs.documents[0])
        uuids = [doc.metadata.chunk_id for doc in similar_docs.documents]
        chunk_docs = self._doc_db.get_class_resources(uuids, ClassResourceChunkDocument)
        return [doc for doc in chunk_docs if isinstance(doc, ClassResourceChunkDocument)]

    def get_class_resources(self, ids: list[UUID]) -> list[ClassResource]:
        """Get the class resources."""
        docs = self._doc_db.get_class_resources(ids, ClassResourceDocument)
        return self.to_api_resources(docs)

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete the class resources."""
        try:
            docs = self._doc_db.get_class_resources(ids)
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

    def create_class_resources(self, class_resources: list[ClassResource]) -> None:
        """Create the class resources."""
        input_docs = self.to_backend_input_docs(class_resources)
        doc_pairs: list[tuple[Indexer, ClassResourceDocument]] = []
        for input_doc in input_docs:
            ingested_doc = Indexer.ingest_document(input_doc)
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

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids)

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

    @staticmethod
    def to_api_resources(documents: list[BaseClassResourceDocument]) -> list[BaseClassResource]:
        """Convert the database documents to API documents."""
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
                output_doc = ClassResourceSnippet(resource_snippet=doc.chunk, **base_doc)
            else:
                raise RuntimeError(f"Unknown document type: {doc}")
            output_documents.append(output_doc)
        return output_documents

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
                output_doc = ClassResourceChunkDocument(chunk=doc.resource_snippet, **base_doc.dict())
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
            converted_chats.append(cls.to_api_chat_message(chat))
        chat_session = APIChatSession(
            id=chat_session.id,
            class_id=chat_session.class_id,
            chats=converted_chats,
        )
        return chat_session

    @classmethod
    def to_api_chat_message(cls, chat_message: BEBaseMessage) -> APIChat:
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
                **msg.dict(exclude={"render_chat"}),
            )
        elif isinstance(chat_message, BEFunctionMessage):
            return APIFunctionChat(
                function_name=chat_message.name,
                render_chat=chat_message.render_chat,
                **msg.dict(exclude={"render_chat"}),
            )
        else:
            raise RuntimeError(f"Unknown chat message type: {chat_message}")