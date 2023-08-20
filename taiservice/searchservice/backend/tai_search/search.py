"""Define the tai_search module."""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Union
from uuid import UUID, uuid4
import traceback
from loguru import logger
from pydantic import BaseModel, Field
from langchain.embeddings import OpenAIEmbeddings
from langchain import document_loaders
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import TextSplitter
from langchain.schema import Document
from pinecone_text.sparse import SpladeEncoder
from .data_ingestors import (
    get_splitter_text_splitter,
    get_page_number,
    get_total_page_count,
    S3ObjectIngestor,
    URLIngestor,
    Ingestor,
)
from .data_ingestor_schema import (
    IngestedDocument,
    InputFormat,
    InputDocument,
    InputDataIngestStrategy,
)
from ..shared_schemas import ChunkMetadata, BaseOpenAIConfig, ClassResourceType
from ..databases.pinecone_db import PineconeDBConfig, PineconeDB
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
        class_resource_document: ClassResourceDocument
    ) -> None:
        """Index a document."""
        try:
            self._s3_prefix = f"{ingested_document.class_id}/{ingested_document.id}/"
            logger.info(f"Loading and splitting document: {ingested_document.id}")
            chunk_documents = self._load_and_split_document(ingested_document)
            logger.info(f"Finished loading and splitting document into {len(chunk_documents)} chunks: {ingested_document.id}")
            class_resource_document.class_resource_chunk_ids = [chunk_doc.id for chunk_doc in chunk_documents]
            logger.info(f"Uploading {len(chunk_documents)} document to cold store: {ingested_document.id}")
            Ingestor.upload_document_to_cold_store(
                bucket_name=self._cold_store_bucket_name,
                ingested_doc=ingested_document,
                chunks=chunk_documents,
            )
            logger.info(f"Finished uploading {len(chunk_documents)}  chunks to cold store: {ingested_document.id}")
            logger.info(f"Embedding {len(chunk_documents)} chunks: {ingested_document.id}")
            vector_documents = self.embed_documents(chunk_documents)
            logger.info(f"Finished embedding {len(chunk_documents)}  chunks: {ingested_document.id}")
            logger.info(f"Loading {len(chunk_documents)}  chunks to db: {ingested_document.id}")
            self._load_class_resources_to_db(class_resource_document, chunk_documents)
            logger.info(f"Finished loading {len(chunk_documents)}  chunks to db: {ingested_document.id}")
            logger.info(f"Loading {len(vector_documents)} vectors to vector store: {ingested_document.id}")
            self._load_vectors_to_vector_store(vector_documents)
            logger.info(f"Finished loading {len(vector_documents)} vectors to vector store: {ingested_document.id}")
        except Exception as e:
            logger.error(traceback.format_exc())
            raise RuntimeError("Failed to index resource.") from e

    def get_relevant_class_resources(self, query: str, class_id: UUID, for_tai_tutor: bool = True) -> list[ClassResourceChunkDocument]:
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
        chunk_doc = ClassResourceChunkDocument(
            class_id=class_id,
            chunk=query,
            full_resource_url="https://www.google.com", # this is a dummy link as it's not needed for the query
            id=uuid4(),
            metadata=ChunkMetadata(
                class_id=class_id,
                title="User Query",
                description="User Query",
                resource_type=ClassResourceType.TEXTBOOK,
            )
        )
        is_search = True if len(query.split()) < 15 else False # assume search if the query is less than 15 words
        alpha = 0.4 if is_search else 0.7 # this is gut feel, we can tune this later, search is likely to use more precise terms
        docs_to_return = 5 if is_search else 3
        pinecone_docs = self.embed_documents(documents=[chunk_doc])
        similar_docs = self._pinecone_db.get_similar_documents(document=pinecone_docs.documents[0], alpha=alpha, doc_to_return=docs_to_return)
        uuids = [doc.metadata.chunk_id for doc in similar_docs.documents]
        chunk_docs = self._document_db.get_class_resources(uuids, ClassResourceChunkDocument, count_towards_metrics=True)
        logger.info(f"Got similar docs: {chunk_docs}")
        return [doc for doc in chunk_docs if isinstance(doc, ClassResourceChunkDocument)]

    def _load_vectors_to_vector_store(self, vector_documents: PineconeDocuments) -> None:
        """Load vectors to vector store."""
        try:
            self._pinecone_db.upsert_vectors(
                documents=vector_documents,
            )
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load vectors to vector store.") from e

    def _load_class_resources_to_db(self, document: ClassResourceDocument, chunk_documents: list[ClassResourceChunkDocument]) -> None:
        """Load the document to the db."""
        chunk_mapping = {
            chunk_doc.id: chunk_doc
            for chunk_doc in chunk_documents
        }
        try:
            failed_docs = self._document_db.upsert_class_resources(
                documents=[document],
                chunk_mapping=chunk_mapping
            )
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
            pattern = f'{character}{{{max_chars_in_a_row},}}'
            document.page_content = re.sub(pattern, character * max_chars_in_a_row, document.page_content)
        return document

    def _load_and_split_document(self, document: IngestedDocument) -> list[ClassResourceChunkDocument]:
        """Split and load a document."""
        split_docs: list[Document] = []
        try:
            Loader: BaseLoader = getattr(document_loaders, document.loading_strategy)
            data_pointer = document.data_pointer
            try:
                # try to treat the pointer as a Path object and resolve it and convert to str
                data_pointer = str(Path(document.data_pointer).resolve())
            except Exception: # pylint: disable=broad-except
                logger.warning(f"Failed to resolve path: {data_pointer}")
            loader: BaseLoader = Loader(data_pointer)
            input_format = document.input_format
            if isinstance(loader, document_loaders.BSHTMLLoader):
                input_format = InputFormat.GENERIC_TEXT # the beautiful soup loader converts html to text so we need to change the input format
            splitter: TextSplitter = get_splitter_text_splitter(input_format)
            split_docs = loader.load_and_split(splitter) # TODO: once we use mathpix, i think we can split pdfs better. Without mathpix, the pdfs don't get split well
        except Exception as e: # pylint: disable=broad-except
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load and split document.") from e
        chunk_documents = []
        total_page_count = get_total_page_count(split_docs)
        ingested_doc_metadata = document.metadata
        ingested_doc_metadata.total_page_count = total_page_count
        for split_doc in split_docs:
            chunk_doc = ClassResourceChunkDocument(
                id=uuid4(),
                chunk=split_doc.page_content,
                metadata=ChunkMetadata(
                    class_id=document.class_id,
                    page_number=get_page_number(split_doc),
                    vector_id=uuid4(),
                    **ingested_doc_metadata.dict(),
                ),
                **document.dict(exclude={"id", "metadata"}),
            )
            chunk_documents.append(chunk_doc)
        return chunk_documents

    def _get_page_number(self, documents: Document, ingested_document: IngestedDocument) -> Optional[int]:
        """Get page number for document."""
        if ingested_document.input_format == InputFormat.PDF:
            return get_page_number(documents)

    def embed_documents(self, documents: Union[list[ClassResourceChunkDocument], ClassResourceChunkDocument]) -> PineconeDocuments:
        """Embed documents."""
        def _embed_batch(batch: list[ClassResourceChunkDocument]) -> list[PineconeDocument]:
            """Embed a batch of documents."""
            texts = [document.chunk for document in batch]
            dense_vectors = self._embedding_strategy.embed_documents(texts)
            vector_docs =  self.vector_document_from_dense_vectors(dense_vectors, batch)
            sparse_vectors = self.get_sparse_vectors(texts)
            for vector_doc, sparse_vector in zip(vector_docs, sparse_vectors):
                vector_doc.sparse_values = sparse_vector
            return vector_docs
        if isinstance(documents, ClassResourceChunkDocument):
            documents = [documents]
        batches = [documents[i : i + self._batch_size] for i in range(0, len(documents), self._batch_size)]
        vector_docs = []
        with ThreadPoolExecutor(max_workers=len(batches)) as executor:
            results = executor.map(_embed_batch, batches)
            vector_docs = [vector_doc for result in results for vector_doc in result]
        class_ids = {doc.metadata.class_id for doc in vector_docs}
        if len(class_ids) != 1: raise RuntimeError(f"All documents must have the same class id. You provided: {class_ids}")
        class_id = class_ids.pop()
        return PineconeDocuments(class_id=class_id, documents=vector_docs)

    @staticmethod
    def get_sparse_vectors(texts: list[str]) -> list[SparseVector]:
        """Add sparse vectors to pinecone."""
        splade = SpladeEncoder()
        vectors = splade.encode_documents(texts)
        sparse_vectors = []
        for vec in vectors:
            sparse_vector = SparseVector.parse_obj(vec)
            sparse_vectors.append(sparse_vector)
        return sparse_vectors

    @staticmethod
    def vector_document_from_dense_vectors(
        dense_vectors: list[list[float]],
        documents: list[ClassResourceChunkDocument],
    ) -> list[PineconeDocument]:
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
            InputDataIngestStrategy.URL_DOWNLOAD: URLIngestor,
        }
        try:
            ingestor = mapping[document.input_data_ingest_strategy]
        except KeyError as e: # pylint: disable=broad-except
            raise NotImplementedError(f"Unsupported input data ingest strategy: {document.input_data_ingest_strategy}") from e
        return ingestor.ingest_data(document, self._cold_store_bucket_name)
