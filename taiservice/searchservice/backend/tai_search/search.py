"""Define the tai_search module."""
import itertools
import os
import re
import copy
from functools import partial
from multiprocessing import current_process
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional, Union
from uuid import UUID, uuid4
import traceback
from time import sleep
import torch
import psutil
from loguru import logger
from pydantic import BaseModel, Field
from langchain.embeddings import OpenAIEmbeddings
from langchain import document_loaders
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import TextSplitter
from langchain.schema import Document
from pinecone_text.sparse import SpladeEncoder
from .data_ingestors import (
    get_text_splitter,
    get_page_number,
    get_total_page_count,
    S3ObjectIngestor,
    WebPageIngestor,
    Ingestor,
    RawUrlIngestor,
)
from .data_ingestor_schema import (
    IngestedDocument,
    InputFomat,
    InputDocument,
    InputDataIngestStrategy,
)
from ..shared_schemas import (
    ChunkMetadata,
    BaseOpenAIConfig,
    ClassResourceType,
    Metadata,
    ChunkSize,
)
from ..databases.pinecone_db import PineconeDBConfig, PineconeDB, PineconeQueryFilter
from ..databases.pinecone_db_schemas import (
    PineconeDocuments,
    PineconeDocument,
    SparseVector,
)
from ..databases.document_db import DocumentDBConfig, DocumentDB
from ..databases.document_db_schemas import (
    ClassResourceChunkDocument,
    ClassResourceDocument,
)
from .resource_utilities import resource_utility_factory, resource_crawler_factory


class OpenAIConfig(BaseOpenAIConfig):
    """Define the OpenAI config."""

    batch_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="The batch size for requests to the OpenAI API.",
    )


class IndexerConfig(BaseModel):
    """Define the tai_search config."""

    pinecone_db_config: PineconeDBConfig = Field(
        ...,
        description="The pinecone db config.",
    )
    document_db_config: DocumentDBConfig = Field(
        ...,
        description="The document db config.",
    )
    openai_config: OpenAIConfig = Field(
        ...,
        description="The OpenAI config.",
    )
    cold_store_bucket_name: str = Field(
        ...,
        description="The name of the cold store bucket.",
    )
    chrome_driver_path: Path = Field(
        ...,
        description="The path to the chrome driver.",
    )


class ResourceLimits(BaseModel):
    """Define the custom parameters for resource usage."""

    memory_percent_threshold: float = Field(
        default=80.0,
        le=80.0,
        description="The threshold for memory usage percentage beyond which system is considered as resource constrained.",
    )
    cpu_percent_threshold: float = Field(
        default=70.0,
        le=80.0,
        description="The threshold for CPU usage percentage beyond which system is considered as resource constrained.",
    )
    additional_memory_gb: float = Field(
        default=3.0,
        ge=3.0,
        description="The safety buffer of memory in GB that needs to be available apart from the estimated memory for batch processing.",
    )


def resources_constrained(resource_limits: ResourceLimits) -> bool:
    """
    Helper function for checking system resources.
    """
    memory_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent()
    available_memory = psutil.virtual_memory().available / 1024 / 1024 / 1024  # convert to GB
    logger.debug(f"Memory usage: {memory_usage}%, CPU usage: {cpu_usage}%, Available memory: {available_memory}GB")
    are_resources_constrained = (
        memory_usage > resource_limits.memory_percent_threshold
        or cpu_usage > resource_limits.cpu_percent_threshold
        or available_memory < resource_limits.additional_memory_gb
    )
    return are_resources_constrained


def execute_with_resource_check(func: Callable[..., Any], resource_limits: ResourceLimits = ResourceLimits()) -> Any:
    """
    Executes the given partial function based on system resource availability.

    This function checks whether system resources are constrained or not before starting the
    resource-intensive process. If resources are constrained, it retries until resources
    are sustainably available.

    Args:
        func: The partial function to be executed.
        resource_limits: An instance of ResourceLimits to customize CPU and memory usage, as well as available memory.

    Returns:
        The function's return value.
    """
    time_to_sleep = 5
    if isinstance(func, partial):
        func_name = func.func.__name__
    else:
        func_name = func.__name__
    while resources_constrained(resource_limits=resource_limits):
        logger.warning(f"System resources constrained. Retrying operation {func_name} after {time_to_sleep} seconds.")
        sleep(time_to_sleep)
    return func()


class TAISearch:
    """Define the tai_search class."""

    def __init__(
        self,
        tai_search_config: IndexerConfig,
    ) -> None:
        """Initialize tai_search."""
        self._pinecone_db = PineconeDB(tai_search_config.pinecone_db_config)
        self._document_db = DocumentDB(tai_search_config.document_db_config)
        self._embedding_strategy = OpenAIEmbeddings(
            openai_api_key=tai_search_config.openai_config.api_key,
            request_timeout=tai_search_config.openai_config.request_timeout,
        )
        self._batch_size = tai_search_config.openai_config.batch_size
        self._cold_store_bucket_name = tai_search_config.cold_store_bucket_name
        self._s3_prefix = ""
        os.environ["PATH"] += f":{tai_search_config.chrome_driver_path}"

    def index_resource(
        self,
        ingested_document: IngestedDocument,
        class_resource_document: ClassResourceDocument,
    ) -> None:
        """Index a document."""
        logger.info(f"Crawling document: {ingested_document.id}")
        try:
            crawler = resource_crawler_factory(ingested_document)
            ingested_documents = crawler.crawl(class_resource_document)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            ingested_documents = [ingested_document]
        logger.info(f"Finished crawling document: {ingested_document.id}. Found {len(ingested_documents)} documents.")

        # TODO: We should not be iterating here, instead crawled docs will have been pushed to a queue that
        # will be consumed by this service so this service is only processing one page/document at a time.
        for ingested_document in ingested_documents:
            utility = resource_utility_factory(self._cold_store_bucket_name, ingested_document)
            logger.info(f"Creating thumbnail for document: {ingested_document.id}")
            ingested_document = utility.create_thumbnail()
            logger.info(f"Finished creating thumbnail for document: {ingested_document.id}")
            logger.info(f"Uploading resource to cold store: {ingested_document.id}")
            ingested_document = utility.upload_resource()
            logger.info(f"Finished uploading resource to cold store: {ingested_document.id}")

            logger.info(f"Loading and splitting document: {ingested_document.id}")
            chunk_documents = self._load_and_split_document(ingested_document, ChunkSize.LARGE)
            chunk_documents.extend(self._load_and_split_document(ingested_document, ChunkSize.SMALL))
            logger.info(f"Finished loading and splitting document into {len(chunk_documents)} chunks: {ingested_document.id}")
            class_resource_document.class_resource_chunk_ids.extend([chunk_doc.id for chunk_doc in chunk_documents])

            logger.info(f"Embedding {len(chunk_documents)} chunks: {ingested_document.id}")
            partial_func = partial(self.embed_documents, chunk_documents)
            vector_documents = execute_with_resource_check(partial_func)
            logger.info(f"Finished embedding {len(chunk_documents)}  chunks: {ingested_document.id}")
            logger.info(f"Loading {len(chunk_documents)}  chunks to db: {ingested_document.id}")
            self._load_class_resources_to_db(class_resource_document, chunk_documents)
            logger.info(f"Finished loading {len(chunk_documents)}  chunks to db: {ingested_document.id}")
            logger.info(f"Loading {len(vector_documents)} vectors to vector store: {ingested_document.id}")
            self._load_vectors_to_vector_store(vector_documents)
            logger.info(f"Finished loading {len(vector_documents)} vectors to vector store: {ingested_document.id}")

    def get_relevant_class_resources(
        self, query: str, class_id: UUID, for_tai_tutor: bool
    ) -> dict[ChunkSize, list[ClassResourceChunkDocument]]:
        """
        Get the most relevant class resources.

        If the for_tai_tutor flag is set, then the results will include the top three
        resources for the class, 1 larger context piece and two shorter snippets. The
        thought behind this is to get context for the topic and then more specific
        examples for the tutor to utilize without spending too many tokens.
        If the for_tai_tutor flag is not set, then the results will include the top
        10 resources for the class as a mixture of larger context pieces and shorter
        snippets (will be about 75/25 where 75 is larger snippets).

        Args:
            query: The query to use to find the most relevant class resources.
            class_id: The class id to search for.
            for_tai_tutor: Whether or not the query is for the TAI Tutor.
        """
        logger.info(f"Getting relevant class resources for query: {query}")
        query_for_small_chunks = ClassResourceChunkDocument(
            class_id=class_id,
            chunk=query,
            full_resource_url="https://www.google.com",  # this is a dummy link as it's not needed for the query
            id=uuid4(),
            preview_image_url="https://www.google.com",  # this is a dummy link as it's not needed for the query
            metadata=ChunkMetadata(
                class_id=class_id,
                title="User Query",
                description="User Query",
                resource_type=ClassResourceType.TEXTBOOK,
                chunk_size=ChunkSize.SMALL,
                chapters=self._extract_chapter_numbers_from_query(query),
                sections=self._extract_section_numbers(query),
            ),
        )
        query_for_large_chunks = copy.deepcopy(query_for_small_chunks)
        query_for_large_chunks.metadata.chunk_size = ChunkSize.LARGE
        queries = [query_for_small_chunks, query_for_large_chunks]
        # TODO: make the resource filter usable
        pinecone_docs = self.embed_documents(documents=queries)
        filters = [
            PineconeQueryFilter(
                filter_by_chapters=True,
                filter_by_sections=True,
                filter_by_resource_type=False,
                alpha=0.5 if for_tai_tutor else 0.7,
            ),
            PineconeQueryFilter(
                filter_by_resource_type=False,
                alpha=0.5 if for_tai_tutor else 0.7,
            ),
        ]

        def compute_similar_documents(params: tuple[PineconeDocument, PineconeQueryFilter]) -> list[PineconeDocument]:
            doc, query_filter = params
            similar_docs = self._pinecone_db.get_similar_documents(document=doc, doc_to_return=50, filter=query_filter)
            alpha = query_filter.alpha
            threshold = (
                alpha * 0.60 + (1 - alpha) * 4.0
            )  # this is a linear interpolation between 0.6 and 4.0, 4.0 is arbitrary as the is technically not an upper limit
            return [doc for doc in similar_docs.documents if doc.score > threshold]

        with ThreadPoolExecutor(max_workers=len(pinecone_docs)) as executor:
            results = executor.map(compute_similar_documents, zip(pinecone_docs.documents, filters))
        relevant_documents = list(itertools.chain(*results))
        uuids = [doc.metadata.chunk_id for doc in relevant_documents]
        chunk_docs = self._document_db.get_class_resources(uuids, ClassResourceChunkDocument, count_towards_metrics=True)
        logger.info(f"Got similar docs: {chunk_docs}")
        chunk_docs = [doc for doc in chunk_docs if isinstance(doc, ClassResourceChunkDocument)]
        chunk_docs = self._sort_chunk_docs_by_pinecone_scores(relevant_documents, chunk_docs)
        return self._group_by_chunk_size(chunk_docs)

    def _upload_docs_to_s3(self, chunk_documents: list[ClassResourceChunkDocument], ingested_document: IngestedDocument) -> None:
        partial_func = partial(
            Ingestor.upload_document_to_cold_store,
            bucket_name=self._cold_store_bucket_name,
            ingested_doc=ingested_document,
            chunks=chunk_documents,
        )
        execute_with_resource_check(partial_func)

    def _group_by_chunk_size(
        self, chunk_documents: list[ClassResourceChunkDocument]
    ) -> dict[ChunkSize, list[ClassResourceChunkDocument]]:
        """Group chunk documents by chunk size."""
        chunk_size_mapping = {
            ChunkSize.SMALL: [],
            ChunkSize.LARGE: [],
        }
        for chunk_doc in chunk_documents:
            chunk_size_mapping[chunk_doc.metadata.chunk_size].append(chunk_doc)
        return chunk_size_mapping

    def _sort_chunk_docs_by_pinecone_scores(
        self,
        pinecone_documents: list[PineconeDocument],
        chunk_documents: list[ClassResourceChunkDocument],
    ) -> list[ClassResourceChunkDocument]:
        """
        Sort chunk documents based on the scores in corresponding Pinecone vector documents.

        Args:
            pinecone_documents: A list of Pinecone vector documents.
            chunk_documents: A list of chunk documents.

        Returns:
            A list of sorted chunk documents.
        """
        # Create a mapping of chunk_id to score from the Pinecone documents.
        score_mapping = {doc.metadata.chunk_id: doc.score for doc in pinecone_documents}
        # Filter out chunk documents without corresponding scores in Pinecone documents and sort the remaining ones.
        filtered_chunk_documents = [doc for doc in chunk_documents if doc.id in score_mapping]
        sorted_chunk_documents = sorted(
            filtered_chunk_documents,
            key=lambda doc: score_mapping[doc.id],
            reverse=True,
        )
        return sorted_chunk_documents

    def _load_vectors_to_vector_store(self, vector_documents: PineconeDocuments) -> None:
        """Load vectors to vector store."""
        try:
            self._pinecone_db.upsert_vectors(
                documents=vector_documents,
            )
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load vectors to vector store.") from e

    def _load_class_resources_to_db(
        self,
        document: ClassResourceDocument,
        chunk_documents: list[ClassResourceChunkDocument],
    ) -> None:
        """Load the document to the db."""
        chunk_mapping = {chunk_doc.id: chunk_doc for chunk_doc in chunk_documents}
        try:
            failed_docs = self._document_db.upsert_class_resources(documents=[document], chunk_mapping=chunk_mapping)
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load document to db.") from e
        if failed_docs:
            raise RuntimeError(f"{len(failed_docs)} documents failed to load to db: {failed_docs}")

    def collapse_spaces_in_document(self, document: Document) -> Document:
        """Collapse spaces in document."""
        max_chars_in_a_row = 3
        characters_to_collapse = ["\n", "\t", " "]
        for character in characters_to_collapse:
            pattern = f"{character}{{{max_chars_in_a_row},}}"
            document.page_content = re.sub(pattern, character * max_chars_in_a_row, document.page_content)
        return document

    def _load_and_split_document(self, document: IngestedDocument, chunk_size: ChunkSize) -> list[ClassResourceChunkDocument]:
        """Split and load a document."""
        # TODO: it's probably a good idea to add this to the resource utilities classes as the chunk urls
        # may need to be dynamically updated, like in the case of YouTube where we need to add a timestamp
        split_docs: list[Document] = []
        try:
            Loader: BaseLoader = getattr(document_loaders, document.loading_strategy)
            data_pointer = document.data_pointer
            if isinstance(data_pointer, Path):
                data_pointer = str(data_pointer.resolve())
            loader: BaseLoader = Loader(data_pointer)
            input_format = document.input_format
            if isinstance(loader, document_loaders.BSHTMLLoader):
                # the beautiful soup loader converts html to text so we need to change the input format
                input_format = InputFomat.GENERIC_TEXT
            splitter: TextSplitter = get_text_splitter(input_format, chunk_size)
            # TODO: once we use mathpix, i think we can split pdfs better. Without mathpix, the pdfs don't get split well
            split_docs = loader.load_and_split(splitter)
        except Exception as e:  # pylint: disable=broad-except
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load and split document.") from e
        chunk_documents = []
        last_chapter = ""
        chapters = []
        for split_doc in split_docs:
            chapters = self._extract_chapter_numbers(split_doc)
            if chapters:
                last_chapter = chapters[-1]
            elif not chapters and last_chapter:
                chapters = [last_chapter]
            chunk_doc = ClassResourceChunkDocument(
                id=uuid4(),
                chunk=split_doc.page_content,
                metadata=ChunkMetadata(
                    class_id=document.class_id,
                    chapters=chapters,
                    sections=self._extract_section_numbers(split_doc),
                    chunk_size=chunk_size,
                    vector_id=uuid4(),
                    **document.metadata.dict(),
                ),
                **document.dict(exclude={"id", "metadata"}),
            )
            chunk_documents.append(chunk_doc)
        return chunk_documents

    def _extract_chapter_numbers_from_query(self, query: str) -> list[str]:
        chapter_pattern = r"(chapters?\s*((\d+\s?[,and\s&]*)+))"  # matches chapter 1, chapter 2, 3, 4, chapter 5 & 6, etc. to extract the numbers from a query
        matches = re.findall(chapter_pattern, query, flags=re.IGNORECASE)
        numbers = []  # List to hold all the chapter numbers
        for match in matches:
            # match is a tuple, the 2nd element contains the string where the numbers are
            sub_matches = re.findall(r"\d+", match[1])  # Extract all the numbers from the second capturing group
            numbers.extend(sub_matches)  # Add the numbers to our list
        # collapse duplicates
        return list(set([str(n) for n in numbers]))

    def _extract_section_numbers(self, document: Union[Document, str]) -> list[str]:
        text = document.page_content if isinstance(document, Document) else document
        section_pattern = r"(\d+(?:\.\d+)*)"  # matches 1, 1.1, 1.2, etc.
        matches = re.findall(section_pattern, text, flags=re.IGNORECASE)
        return list(set(matches))

    def _extract_chapter_numbers(self, document: Union[Document, str]) -> list[str]:
        text = document.page_content if isinstance(document, Document) else document
        chapter_pattern = r"((?<=\s)|^)chapter\s*(\d+)(?=[\s:])"
        matches = re.findall(chapter_pattern, text, flags=re.IGNORECASE)
        unique_headings = list(set(match[1] for match in matches))
        return unique_headings

    def _get_page_number(self, document: Document, ingested_document: IngestedDocument) -> Optional[int]:
        """Get page number for document."""
        if ingested_document.input_format == InputFomat.PDF:
            return get_page_number(document)

    def embed_documents(
        self,
        documents: Union[list[ClassResourceChunkDocument], ClassResourceChunkDocument],
    ) -> PineconeDocuments:
        """Embed documents."""
        if isinstance(documents, ClassResourceChunkDocument):
            documents = [documents]
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device '{device}' for vector encoding.")

        def _embed_batch(
            batch: list[ClassResourceChunkDocument],
        ) -> list[PineconeDocument]:
            """Embed a batch of documents."""
            texts = [document.chunk for document in batch]
            dense_vectors = self._embedding_strategy.embed_documents(texts)
            vector_docs = self.vector_document_from_dense_vectors(dense_vectors, batch)
            return vector_docs

        if isinstance(documents, ClassResourceChunkDocument):
            documents = [documents]
        batches = [documents[i : i + self._batch_size] for i in range(0, len(documents), self._batch_size)]
        vector_docs = []
        with ThreadPoolExecutor(max_workers=len(batches)) as executor:
            results = executor.map(_embed_batch, batches)
            vector_docs = [vector_doc for result in results for vector_doc in result]
        sparse_vectors = self.get_sparse_vectors([doc.chunk for doc in documents])
        for vector_doc, sparse_vector in zip(vector_docs, sparse_vectors):
            vector_doc.sparse_values = sparse_vector
        class_ids = {doc.metadata.class_id for doc in vector_docs}
        if len(class_ids) != 1:
            raise RuntimeError(f"All documents must have the same class id. You provided: {class_ids}")
        class_id = class_ids.pop()
        return PineconeDocuments(class_id=class_id, documents=vector_docs)

    @staticmethod
    def get_sparse_vectors(texts: list[str]) -> list[SparseVector]:
        """Add sparse vectors to pinecone."""
        batch_size = 50
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        logger.info(f"Splitting {len(texts)} documents into {len(batches)} batches.")
        sparse_vectors = []
        device = "cuda" if torch.cuda.is_available() else "cpu"
        splade = SpladeEncoder(device=device)
        for i, batch in enumerate(batches):
            logger.debug(f"Processing batch {i + 1} of {len(batches)} with {len(batch)} documents in pid {current_process().pid}")
            partial_func = partial(splade.encode_documents, batch)
            gb_for_batch = max(
                len(batch) / 50, 3
            )  # this is a rough estimate of the memory needed for the batch based on experience
            vectors = execute_with_resource_check(partial_func, ResourceLimits(additional_memory_gb=gb_for_batch))
            sparse_vectors = [SparseVector.parse_obj(vec) for vec in vectors]
            sparse_vectors.extend(sparse_vectors)
        return sparse_vectors

    @staticmethod
    def vector_document_from_dense_vectors(
        dense_vectors: list[list[float]],
        documents: list[ClassResourceChunkDocument],
    ) -> list[PineconeDocument]:
        """Create a vector document from dense vectors."""
        vector_docs = []
        for dense_vector, document in zip(dense_vectors, documents):
            doc = PineconeDocument(
                id=document.metadata.vector_id,
                metadata=ChunkMetadata.parse_obj(document.metadata),
                values=dense_vector,
            )
            vector_docs.append(doc)
        return vector_docs

    def ingest_document(self, document: InputDocument) -> IngestedDocument:
        """Ingest a document."""
        mapping: dict[InputDataIngestStrategy, Ingestor] = {
            InputDataIngestStrategy.S3_FILE_DOWNLOAD: S3ObjectIngestor,
            InputDataIngestStrategy.URL_DOWNLOAD: WebPageIngestor,
            InputDataIngestStrategy.RAW_URL: RawUrlIngestor,
        }
        try:
            ingestor = mapping[document.input_data_ingest_strategy]
        except KeyError as e:  # pylint: disable=broad-except
            raise NotImplementedError(f"Unsupported input data ingest strategy: {document.input_data_ingest_strategy}") from e
        return ingestor.ingest_data(document, self._cold_store_bucket_name)

    @staticmethod
    def get_input_document_ingest_strategy(url: str) -> InputDataIngestStrategy:
        if re.match(r"https://.*\.s3\.amazonaws\.com/.*", url):
            return InputDataIngestStrategy.S3_FILE_DOWNLOAD
        elif RawUrlIngestor.is_raw_url(url):
            return InputDataIngestStrategy.RAW_URL
        else:
            return InputDataIngestStrategy.URL_DOWNLOAD
