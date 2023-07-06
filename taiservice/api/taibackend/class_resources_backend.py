"""Define the class resources backend."""
from typing import Any, Union
import json
from uuid import UUID
from loguru import logger
import boto3
from botocore.exceptions import ClientError
try:
    from taiservice.api.runtime_settings import TaiApiSettings
    from ..routers.class_resources_schema import ClassResource, ClassResources, Metadata
    from .databases.document_db_schemas import ClassResourceDocument, ClassResourceChunkDocument
    from .databases.document_db import DocumentDB, DocumentDBConfig
    from .databases.pinecone_db import PineconeDB, PineconeDBConfig
    from .indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        InputDataIngestStrategy,
        OpenAIConfig,
    )
except ImportError:
    from runtime_settings import TaiApiSettings
    from routers.class_resources_schema import ClassResource, ClassResources, Metadata
    from taibackend.databases.document_db_schemas import ClassResourceDocument, ClassResourceChunkDocument
    from taibackend.databases.document_db import DocumentDB, DocumentDBConfig
    from taibackend.databases.pinecone_db import PineconeDB, PineconeDBConfig
    from taibackend.indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        InputDataIngestStrategy,
        OpenAIConfig,
    )

class ClassResourcesBackend:
    """Class to handle the class resources backend."""
    def __init__(self, runtime_settings: TaiApiSettings) -> None:
        """Initialize the class resources backend."""
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
        openAI_config = OpenAIConfig(
            api_key=self._get_secret_value(runtime_settings.openAI_api_key_secret_name),
            batch_size=runtime_settings.openAI_batch_size,
            request_timeout=runtime_settings.openAI_request_timeout,
        )
        self._indexer_config = IndexerConfig(
            pinecone_db_config=self._pinecone_db_config,
            document_db_config=self._doc_db_config,
            openai_config=openAI_config,
        )

    def get_class_resources(self, ids: list[UUID]) -> list[ClassResourceDocument]:
        """Get the class resources."""
        return self._doc_db.get_class_resources(ids, ClassResourceDocument)

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete the class resources."""
        try:
            docs = self._doc_db.get_class_resources(ids)
            for doc in docs:
                if isinstance(doc, ClassResourceDocument) or isinstance(doc, ClassResourceChunkDocument):
                    if isinstance(doc, ClassResourceDocument):
                        chunk_docs = self._chunks_from_class_resource(doc)
                    chunk_docs = [doc]
                    self._delete_vectors_from_chunks(chunk_docs)
            self._doc_db.delete_class_resources(docs)
        except Exception as e:
            logger.critical(f"Failed to delete class resources: {e}")
            raise RuntimeError(f"Failed to delete class resources: {e}") from e

    def _is_s3_url(self, url: str) -> bool:
        """Return True if the url is an S3 url."""
        return url.startswith('s3://')

    def create_class_resources(self, class_resources: list[ClassResourceDocument]) -> None:
        """Create the class resources."""
        indexer = Indexer(self._indexer_config)
        for class_resource in class_resources:
            if self._is_s3_url(class_resource.full_resource_url):
                ingest_strategy = InputDataIngestStrategy.S3_FILE_DOWNLOAD
            else:
                ingest_strategy = InputDataIngestStrategy.URL_DOWNLOAD
            input_doc = InputDocument(
                input_data_ingest_strategy=ingest_strategy,
                **class_resource.dict()
            )
            indexer.index_resource(input_doc)

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids)

    def _delete_vectors_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> None:
        """Delete the vectors from the chunks."""
        vector_ids = [chunk.vector_id for chunk in chunks]
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

    def convert_database_documents_to_api_documents(self, documents: list[ClassResourceDocument]) -> list[ClassResource]:
        """Convert the database documents to API documents."""
        output_documents = []
        for doc in documents:
            metadata = doc.metadata
            output_doc = ClassResource(
                id=doc.id,
                class_id=doc.class_id,
                full_resource_url=doc.full_resource_url,
                preview_image_url=doc.preview_image_url,
                status=doc.status,
                metadata=Metadata(
                    title=metadata.title,
                    description=metadata.description,
                    tags=metadata.tags,
                    resource_type=metadata.resource_type,
                )
            )
            output_documents.append(output_doc)
        return output_documents