"""Define the backend for handling requests to the TAI Search Service."""
from datetime import date, datetime, timedelta
from hashlib import sha1
import json
import traceback
from uuid import uuid4
from typing import Any, Callable, Optional, Type, Union
from uuid import UUID
import psutil
import boto3
from botocore.exceptions import ClientError
from loguru import logger
from redis import (
    RedisCluster,
    Redis,
    retry as redis_retry,
    backoff as redis_backoff,
)
from taiservice.api.taibackend.shared_schemas import SearchEngineResponse
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
    SearchQuery,
)
from .errors import ServerOverloadedError
from ..runtime_settings import SearchServiceSettings
from .databases.document_db import DocumentDB, DocumentDBConfig
from .databases.document_db_schemas import (
    ClassResourceDocument,
    BaseClassResourceDocument,
    ClassResourceChunkDocument,
    ChunkMetadata as BEChunkMetadata,
    StatefulClassResourceDocument,
    IngestedDocument,
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
    ClassResourceProcessingStatus,
    ChunkSize,
    Cache,
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
        ClusterClass = Redis if runtime_settings.cache_host_name == "localhost" else RedisCluster
        # the backoff is configured with the fact that the checking interval for the mathpix api is 5 seconds
        cache_instance = ClusterClass(
            host=runtime_settings.cache_host_name,
            port=runtime_settings.port_for_all_cache_hosts,
            decode_responses=True,
            retry=redis_retry.Retry(
                retries=5,
                backoff=redis_backoff.ExponentialBackoff(
                    base=0.1,
                    cap=1,
                ),
            ),
        )
        cache = Cache(instance=cache_instance)
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
            cache=cache,
        )
        self._tai_search = tai_search.TAISearch(self._tai_search_config)
        self._metrics = Metrics(
            MetricsConfig(
                document_db_instance=self._doc_db,
            )
        )

    @staticmethod
    def log_system_health() -> None:
        """Log the system health."""
        cpu_load = psutil.cpu_percent(interval=1)
        svmem = psutil.virtual_memory()
        mem_available_GB = svmem.available / 1024**3
        memory_usage = svmem.percent
        logger.debug(f"Memory usage: {memory_usage}%, CPU usage: {cpu_load}%, Available memory: {mem_available_GB}GB")

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
                input_data_ingest_strategy=tai_search.TAISearch.get_input_document_ingest_strategy(resource.full_resource_url),
                metadata=DBResourceMetadata(
                    title=metadata.title,
                    description=metadata.description,
                    tags=metadata.tags,
                    resource_type=metadata.resource_type,
                ),
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
                    page_number=metadata.page_number,
                ),
            ).dict(exclude={"raw_snippet_url", "parent_resource_url"})
            if isinstance(doc, ClassResourceDocument):
                output_doc = ClassResource(
                    status=doc.status,
                    raw_snippet_url=doc.raw_chunk_url,
                    parent_resource_url=doc.parent_resource_url,
                    **base_doc,
                )
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
                output_doc = ClassResourceChunkDocument(chunk=doc.resource_snippet, **base_doc.dict())
            else:
                raise RuntimeError(f"Unknown document type: {doc}")
            output_documents.append(output_doc)
        return output_documents

    def create_class_resource(self, class_resource: ClassResource) -> tuple[Callable[[], None], ClassResource]:
        """Create the class resources."""
        if not self._is_server_ready():
            raise ServerOverloadedError("Server is overloaded, please try again later.")
        input_doc = self.to_backend_input_docs(class_resource)[0]
        ingested_doc = self._tai_search.ingest_document(input_doc)
        ingested_doc.id = uuid4()
        if not self._able_to_create_resource(ingested_doc):
            raise DuplicateClassResourceError(f"Duplicate class resource: {ingested_doc.id} in class {ingested_doc.class_id}")
        self._coerce_and_update_status(ingested_doc, ClassResourceProcessingStatus.PENDING)

        def index_resource() -> None:
            try:
                self._delete_if_exists(ingested_doc)
                self._coerce_and_update_status(ingested_doc, ClassResourceProcessingStatus.PROCESSING)
                db_class_resource = self._tai_search.index_resource(ingested_doc)
                self._coerce_and_update_status(db_class_resource, ClassResourceProcessingStatus.COMPLETED)
                logger.info(f"Completed indexing class resource: {db_class_resource.id}")
            except Exception:  # pylint: disable=broad-except
                self._coerce_and_update_status(ingested_doc, ClassResourceProcessingStatus.FAILED)
                logger.critical(f"Failed to create class resources")
                logger.critical(traceback.format_exc())

        api_resource = self.to_api_resources(ClassResourceDocument(**ingested_doc.dict()))
        return index_resource, api_resource

    def get_class_resources(self, ids: list[UUID], from_class_ids: bool = False) -> list[ClassResource]:
        """Get the class resources."""
        docs = self._doc_db.get_class_resources(ids, ClassResourceDocument, from_class_ids=from_class_ids)
        for doc in docs:
            if self._is_resource_stuck_processing(doc.id):
                self._coerce_and_update_status(doc, ClassResourceProcessingStatus.FAILED)
        return self.to_api_resources(docs)

    def _delete_if_exists(self, new_doc: tai_search.IngestedDocument) -> None:
        """Delete the class resources before updating."""
        _, existing_doc = self._is_duplicate_class_resource(new_doc)
        if existing_doc:
            self.delete_class_resource(existing_doc)

    def delete_class_resource(self, resource: ClassResourceDocument) -> None:
        """Delete the class resources."""
        try:
            # because we have chosen a flat structure, we do not need to recursively delete the chunks
            self._coerce_and_update_status(resource, ClassResourceProcessingStatus.DELETING)
            child_docs = self._doc_db.get_class_resources(resource.child_resource_ids, ClassResourceDocument)
            for child_doc in child_docs:
                chunk_docs = self._chunks_from_class_resource(child_doc)
                self._delete_vectors_from_chunks(chunk_docs, resource.class_id)
                self._doc_db.delete_class_resources(chunk_docs)
                self._doc_db.delete_class_resources(child_doc)
            self._doc_db.delete_class_resources(resource)
        except Exception as e:
            logger.critical(f"Failed to delete class resources: {e}")
            self._coerce_and_update_status(resource, ClassResourceProcessingStatus.FAILED)
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
            date_range=APIDateRange(
                start_date=frequent_resources.date_range.start_date, end_date=frequent_resources.date_range.end_date
            ),
            resources=[resource.dict() for resource in ranked_resources],
        )
        return resources

    def search(self, search_query: SearchQuery, for_tai_tutor: bool) -> tuple[SearchEngineResponse, Optional[Callable]]:
        """Search for class resources."""
        if isinstance(search_query, ResourceSearchQuery):
            resource_types = search_query.filters.resource_types
        else:
            resource_types = None
        chunk_docs = self._tai_search.get_relevant_class_resources(
            search_query.query,
            search_query.class_id,
            for_tai_tutor,
            resource_types=resource_types,
        )
        small_chunks = self._get_chunks(chunk_docs, ChunkSize.SMALL)
        large_chunks = self._get_chunks(chunk_docs, ChunkSize.LARGE)
        resource_ids = self._get_resource_ids_from_chunks(chunk_docs)
        # When retrieving for TAI tutor, the class resources are never used, so we don't need to retrieve them to improve response time
        resource_docs = [] if for_tai_tutor else self._doc_db.get_class_resources(resource_ids, ClassResourceDocument)
        self._replace_urls_with_chunk_urls(resource_docs, chunk_docs)
        sorted_resources = self._sort_class_resources(resource_docs, chunk_docs)

        search_results = SearchEngineResponse(
            short_snippets=self.to_api_resources(small_chunks),
            long_snippets=self.to_api_resources(large_chunks),
            class_resources=self.to_api_resources(sorted_resources),
            **search_query.dict(),
        )

        def update_metric():
            chunk_docs_truncated = chunk_docs[:3]
            logger.debug(f"Updating metrics for {len(chunk_docs_truncated)} chunk documents")
            self._metrics.upsert_metrics_for_docs([doc.id for doc in chunk_docs_truncated], ClassResourceChunkDocument)
            logger.debug(f"Finished updating metrics for {len(chunk_docs_truncated)} chunk documents")
            logger.debug(f"Updating metrics for {len(resource_ids)} resource documents")
            self._metrics.upsert_metrics_for_docs(resource_ids, ClassResourceDocument)
            logger.debug(f"Finished updating metrics for {len(resource_ids)} resource documents")

        return search_results, update_metric

    def _replace_urls_with_chunk_urls(
        self, resource_docs: list[ClassResourceDocument], chunk_docs: list[ClassResourceChunkDocument]
    ) -> None:
        resource_dict = {resource.id: resource for resource in resource_docs}
        resources_docs_already_replaced = set()
        for chunk_doc in chunk_docs:
            resource = resource_dict.get(chunk_doc.resource_id)
            if resource and resource.id not in resources_docs_already_replaced:
                if chunk_doc.raw_chunk_url:
                    resources_docs_already_replaced.add(resource.id)
                    resource.raw_chunk_url = chunk_doc.raw_chunk_url

    def _get_resource_ids_from_chunks(
        self, docs: Union[list[ClassResourceChunkDocument], ClassResourceChunkDocument], unique: bool = True
    ) -> list[UUID]:
        """Get the parent ids from the chunks."""
        if isinstance(docs, ClassResourceChunkDocument):
            docs = [docs]
        resource_ids = [doc.resource_id for doc in docs]
        return list(set(resource_ids)) if unique else resource_ids

    def _get_chunks(
        self,
        chunk_documents: list[ClassResourceChunkDocument],
        chunk_size: ChunkSize,
    ) -> list[ClassResourceChunkDocument]:
        """Group chunk documents by chunk size."""
        chunk_documents = [chunk for chunk in chunk_documents if chunk.metadata.chunk_size == chunk_size]
        return chunk_documents

    def _sort_class_resources(
        self,
        class_resources: list[ClassResourceDocument],
        chunk_documents: list[ClassResourceChunkDocument],
    ) -> list[ClassResourceDocument]:
        """Rank class resources based on the order of the ChunkDocuments."""
        resource_dict = {resource.id: resource for resource in class_resources}
        sorted_resources = []
        already_sorted_resources = set()
        for chunk_doc in chunk_documents:
            resource = resource_dict.get(chunk_doc.resource_id)
            if resource and resource.id not in already_sorted_resources:
                already_sorted_resources.add(resource.id)
                sorted_resources.append(resource)
        return sorted_resources

    def _is_server_ready(self) -> bool:
        cpu_load = psutil.cpu_percent(interval=1)
        svmem = psutil.virtual_memory()
        mem_available_MB = svmem.available / 1024**2
        mem_percent = svmem.percent
        if cpu_load > 98 or mem_percent > 98 or mem_available_MB < 1000:
            return False
        return True

    def _get_secret_value(self, secret_name: str) -> Union[dict[str, Any], str]:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager")
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            raise RuntimeError(f"Failed to get secret value: {e}") from e
        secret = get_secret_value_response["SecretString"]
        try:
            return json.loads(secret)
        except json.JSONDecodeError:
            return secret

    def _able_to_create_resource(
        self, new_doc: tai_search.IngestedDocument, class_resource_docs: Optional[list[ClassResourceDocument]] = None
    ) -> bool:
        """Check if the class resource is stuck uploading."""
        if not class_resource_docs:
            class_resource_docs: list[ClassResourceDocument] = self._doc_db.get_class_resources(  # type: ignore
                new_doc.class_id,
                ClassResourceDocument,
                from_class_ids=True,
            )
        statuses_allowed_to_proceed = [
            ClassResourceProcessingStatus.FAILED,
        ]
        is_duplicate, duplicate_doc = self._is_duplicate_class_resource(new_doc, class_resource_docs)
        if is_duplicate:
            if duplicate_doc and duplicate_doc.status in statuses_allowed_to_proceed:
                return True
            return False
        return True

    def _is_resource_stuck_processing(self, resource_id: UUID) -> bool:
        class_resource_docs = self._doc_db.get_class_resources(
            resource_id,
            ClassResourceDocument,
            from_class_ids=True,
        )
        existing_doc = class_resource_docs[0] if class_resource_docs else None
        if not existing_doc:
            return False

        assert isinstance(existing_doc, ClassResourceDocument)
        if existing_doc.status != ClassResourceProcessingStatus.COMPLETED:
            elapsed_time = (datetime.utcnow() - existing_doc.modified_timestamp).total_seconds()
            if elapsed_time > self._runtime_settings.class_resource_processing_timeout:
                return True
        return False

    def _is_duplicate_class_resource(
        self, new_doc: tai_search.IngestedDocument, class_resource_docs: Optional[list[ClassResourceDocument]] = None
    ) -> tuple[bool, Optional[ClassResourceDocument]]:
        if not class_resource_docs:
            class_resource_docs: list[ClassResourceDocument] = self._doc_db.get_class_resources(  # type: ignore
                new_doc.class_id,
                ClassResourceDocument,
                from_class_ids=True,
            )
        doc_hashes = {
            class_resource_doc.hashed_document_contents: class_resource_doc for class_resource_doc in class_resource_docs
        }
        doc_titles = {class_resource_doc.metadata.title: class_resource_doc for class_resource_doc in class_resource_docs}
        existing_doc = doc_hashes.get(new_doc.hashed_document_contents) or doc_titles.get(new_doc.metadata.title)
        if existing_doc:
            return True, existing_doc
        return False, None

    def _coerce_and_update_status(
        self,
        docs: Union[list[StatefulClassResourceDocument], StatefulClassResourceDocument],
        status: ClassResourceProcessingStatus,
    ) -> None:
        """Coerce the status of the class resources to the given status and update the database."""
        if isinstance(docs, StatefulClassResourceDocument):
            docs = [docs]
        stateful_resources = [ClassResourceDocument(**doc.dict()) for doc in docs]
        self._coerce_status_to(stateful_resources, status)
        self._doc_db.update_statuses(stateful_resources)

    def _coerce_status_to(
        self, class_resources: list[StatefulClassResourceDocument], status: ClassResourceProcessingStatus
    ) -> None:
        """Coerce the status of the class resources to the given status."""
        for class_resource in class_resources:
            class_resource.status = status

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids, ClassResourceChunkDocument)

    def _delete_vectors_from_chunks(self, chunks: list[ClassResourceChunkDocument], class_id: UUID) -> None:
        """Delete the vectors from the chunks."""
        vector_ids = [chunk.metadata.vector_id for chunk in chunks]
        self._pinecone_db.delete_vectors(vector_ids, class_id)

    def _get_BE_date_range(self, start_date: Optional[date], end_date: Optional[date]) -> BEDateRange:
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=7)
        if end_date is None:
            end_date = datetime.utcnow()
        return BEDateRange(start_date=start_date, end_date=end_date)
