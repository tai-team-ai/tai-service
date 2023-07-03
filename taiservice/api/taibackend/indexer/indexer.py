"""Define the indexer module."""
from enum import Enum
from pydantic import BaseModel, Field
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document
try:
    from taiservice.api.taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taiservice.api.taibackend.databases.document_db import DocumentDBConfig, DocumentDB
    from taiservice.api.taibackend.databases.document_db_schemas import (
        BaseClassResourceDocument,
    )
except ImportError:
    from taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taibackend.databases.document_db import DocumentDBConfig, DocumentDB
    from taibackend.databases.document_db_schemas import BaseClassResourceDocument


class SupportedInputFormat(str, Enum):
    """Define the supported input formats."""

    PDF = "pdf"

class LoadingStrategy(str, Enum):
    """Define the loading strategies."""

    PyMuPDF = "PyMuPDF"

LOADING_STRATEGY_MAPPING = {
    SupportedInputFormat.PDF: LoadingStrategy.PyMuPDF,
}

class InputDataIngestStrategy(str, Enum):
    """Define the input types."""

    S3 = "s3"
    WEB_CRAWL = "web_crawl"
    NOT_APPLICABLE = "not_applicable"


class InputDocument(BaseClassResourceDocument, Document):
    """Define the input document."""

    page_content: str = Field(
        default="",
        description="The content of the document.",
    )
    input_location: InputDataIngestStrategy = Field(
        ...,
        description="The location of the input data.",
    )

class OpenAIConfig(BaseModel):
    """Define the OpenAI config."""

    api_key: str = Field(
        ...,
        description="The API key of the OpenAI API.",
    )
    request_timeout: int = Field(
        ...,
        le=30,
        description="The timeout for requests to the OpenAI API.",
    )

class IndexerConfig(BaseModel):
    """Define the indexer config."""

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

class Indexer:
    """Define the indexer class."""

    def __init__(
        self,
        indexer_config: IndexerConfig,
    ) -> None:
        """Initialize indexer."""
        self._pinecone_db = PineconeDB(indexer_config.pinecone_db_config)
        self._document_db = DocumentDB(indexer_config.document_db_config)
        self._embedding_strategy = OpenAIEmbeddings(
            openai_api_key=indexer_config.openai_config.api_key,
            request_timeout=indexer_config.openai_config.request_timeout,
        )

    def index_resource(self, document: InputDocument) -> None:
        """Index a document."""


    def _ingest_document(self, document: InputDocument) -> None:
        """Ingest a document."""
        if document.input_location == InputDataIngestStrategy.S3:
            raise NotImplementedError
        elif document.input_location == InputDataIngestStrategy.WEB_CRAWL:
            raise NotImplementedError
        elif document.input_location == InputDataIngestStrategy.NOT_APPLICABLE:
            raise NotImplementedError
        else:
            raise NotImplementedError

