"""Define the backend for handling requests to the TAI Search Service."""
from datetime import date, datetime, timedelta
import json
from typing import Any, Optional, Union
from uuid import UUID
import psutil
import boto3
from botocore.exceptions import ClientError
from loguru import logger

from .errors import ServerOverloadedError
from taiservice.api.routers.class_resources_schema import (
    ClassResource,
    ClassResources,
    BaseClassResource as APIBaseClassResource,
    Metadata as APIResourceMetadata,
)
from taiservice.api.routers.common_resources_schema import (
    FrequentlyAccessedResources as APIFrequentlyAccessedResources,
    FrequentlyAccessedResource as APIFrequentlyAccessedResource,
    DateRange as APIDateRange,
)
from taiservice.api.routers.tai_schemas import (
    ClassResourceSnippet as APIClassResourceSnippet,
    ResourceSearchQuery,
    SearchResults,
)
from ..runtime_settings import SearchServiceSettings
from .databases.document_db import DocumentDB, DocumentDBConfig
from .databases.document_db_schemas import (
    ClassResourceProcessingStatus,
    ClassResourceDocument,
    BaseClassResourceDocument,
    ClassResourceChunkDocument,
    ChunkMetadata as BEChunkMetadata,
)
from .databases.pinecone_db import PineconeDB, PineconeDBConfig
from .metrics import (
    MetricsConfig,
    Metrics,
    DateRange as BEDateRange,
)
from .databases.errors import DuplicateClassResourceError
from .shared_schemas import (
    Metadata as DBResourceMetadata,
) 
from .tai_search import search as tai_search


class Backend:
    """Class to handle the class resources backend."""

    def __init__(self, runtime_settings: SearchServiceSettings) -> None:
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
        openAI_config = tai_search.OpenAIConfig(
            api_key=self._openai_api_key,
            batch_size=runtime_settings.openAI_batch_size,
            request_timeout=runtime_settings.openAI_request_timeout,
        )
        self._tai_search_config = tai_search.IndexerConfig(
            pinecone_db_config=self._pinecone_db_config,
            document_db_config=self._doc_db_config,
            openai_config=openAI_config,
            cold_store_bucket_name=runtime_settings.cold_store_bucket_name,
            chrome_driver_path=runtime_settings.chrome_driver_path,
        )
        self._tai_search = tai_search.TAISearch(self._tai_search_config)
        self._metrics = Metrics(
            MetricsConfig(
                document_db_instance=self._doc_db,
            )
        )

    @staticmethod
    def to_backend_input_docs(resources: Union[ClassResources, ClassResource]) -> list[tai_search.InputDocument]:
        """Convert the API documents to database documents."""
        input_documents = []
        if isinstance(resources, ClassResource):
            resources = [resources]
        elif isinstance(resources, ClassResources):
            resources = resources.class_resources
        else:
            raise RuntimeError(f"Unknown document type: {resources}")
        for resource in resources:
            metadata = resource.metadata
            input_doc = tai_search.InputDocument(
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

    @staticmethod
    def to_api_resources(
        documents: Union[list[BaseClassResourceDocument], BaseClassResourceDocument],
    ) -> Union[list[APIBaseClassResource], APIBaseClassResource]:
        """Convert the database documents to API documents."""
        input_was_list = isinstance(documents, list)
        if isinstance(documents, BaseClassResourceDocument):
            documents = [documents]
            input_was_list = False
        output_documents = []
        for doc in documents:
            metadata = doc.metadata
            base_doc = APIBaseClassResource(
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
                output_doc = APIClassResourceSnippet(resource_snippet=doc.chunk, raw_snippet_url=doc.raw_chunk_url, **base_doc)
            else:
                raise RuntimeError(f"Unknown document type: {doc}")
            output_documents.append(output_doc)
        return output_documents if input_was_list else output_documents[0]

    @staticmethod
    def to_backend_resources(documents: list[APIBaseClassResource]) -> list[BaseClassResourceDocument]:
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
            elif isinstance(doc, APIClassResourceSnippet):
                base_doc.metadata = BEChunkMetadata(
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

    def create_class_resource(self, class_resource: ClassResource) -> callable:
        """Create the class resources."""
        if not self._is_server_ready():
            raise ServerOverloadedError("Server is overloaded, please try again later.")
        input_doc = self.to_backend_input_docs(class_resource)[0]
        ingested_doc = self._tai_search.ingest_document(input_doc)
        if self._is_stuck_processing(ingested_doc.id): # if it's stuck, we should continue as the operations are idempotent
            pass
        elif self._is_duplicate_class_resource(ingested_doc):
            raise DuplicateClassResourceError(f"Duplicate class resource: {ingested_doc.id} in class {ingested_doc.class_id}")
        class_resource = ClassResourceDocument.from_ingested_doc(ingested_doc)
        self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.PENDING)
        def index_resource() -> None:
            try:
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.PROCESSING)
                self._tai_search.index_resource(ingested_doc, class_resource)
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.COMPLETED)
                logger.info(f"Completed indexing class resource: {class_resource.id}")
            except Exception as e: # pylint: disable=broad-except
                logger.critical(f"Failed to create class resources: {e}")
                self._coerce_and_update_status(class_resource, ClassResourceProcessingStatus.FAILED)
        return index_resource

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

    def search(self, search_query: ResourceSearchQuery, for_tai_tutor: bool) -> SearchResults:
        """Search for class resources."""
        docs = self._tai_search.get_relevant_class_resources(search_query.query, search_query.class_id, for_tai_tutor)
        docs = self.to_api_resources(docs)
        search_results = SearchResults(
            suggested_resources=docs[:4],
            other_resources=docs[4:],
            **search_query.dict(),
        )
        return search_results

    def _is_server_ready(self) -> bool:
        cpu_load = psutil.cpu_percent(interval=1)
        svmem = psutil.virtual_memory()
        mem_available_MB = svmem.available / 1024 ** 2
        mem_percent = svmem.percent
        if cpu_load > 99 or mem_percent > 95 or mem_available_MB < 1000:
            return False
        return True

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

    def _is_stuck_processing(self, doc_id: UUID) -> bool:
        """Check if the class resource is stuck uploading."""
        class_resource_docs: list[ClassResourceDocument] = self._doc_db.get_class_resources(
            doc_id,
            ClassResourceDocument,
            count_towards_metrics=False
        )
        existing_doc = class_resource_docs[0] if class_resource_docs else None
        if not existing_doc:
            return False
        stable = existing_doc.status == ClassResourceProcessingStatus.COMPLETED \
            or existing_doc.status == ClassResourceProcessingStatus.FAILED
        if not stable:
            elapsed_time = (datetime.utcnow() - existing_doc.modified_timestamp).total_seconds()
            if elapsed_time > self._runtime_settings.class_resource_processing_timeout:
                return True
        return False

    def _is_duplicate_class_resource(self, new_doc: tai_search.IngestedDocument) -> bool:
        """Check if the document can be created."""
        class_resource_docs = self._doc_db.get_class_resources(
            new_doc.class_id,
            ClassResourceDocument,
            from_class_ids=True,
            count_towards_metrics=False
        )
        docs = {doc.id: doc for doc in class_resource_docs}
        doc_hashes = set([class_resource_doc.hashed_document_contents for class_resource_doc in class_resource_docs])
        # find the doc and check the status, if failed, then we can overwrite
        existing_doc = docs.get(new_doc.id, None)
        if existing_doc and existing_doc.status == ClassResourceProcessingStatus.FAILED:
            return False
        return new_doc.hashed_document_contents in doc_hashes

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

    def _coerce_status_to(self, class_resources: list[ClassResourceDocument], status: ClassResourceProcessingStatus) -> None:
        """Coerce the status of the class resources to the given status."""
        for class_resource in class_resources:
            class_resource.status = status

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids, ClassResourceChunkDocument, count_towards_metrics=False)

    def _delete_vectors_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> None:
        """Delete the vectors from the chunks."""
        vector_ids = [chunk.metadata.vector_id for chunk in chunks]
        self._pinecone_db.delete_vectors(vector_ids)

    def _get_BE_date_range(self, start_date: Optional[date], end_date: Optional[date]) -> BEDateRange:
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.utcnow()
        return BEDateRange(start_date=start_date, end_date=end_date)