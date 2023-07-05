"""Define data ingestors used by the indexer."""
from abc import ABC
from enum import Enum
from pathlib import Path
import traceback
from typing import Any, Optional
import filetype
from bs4 import BeautifulSoup
import boto3
from loguru import logger
from pydantic import Field, validator
from langchain.text_splitter import Language
from langchain.text_splitter import TextSplitter, RecursiveCharacterTextSplitter
from langchain import text_splitter
from langchain.schema import Document
import requests
# first imports are for local development, second imports are for deployment
try:
    from ..databases.document_db_schemas import (
        BaseClassResourceDocument
    )
except ImportError:
    from taibackend.databases.document_db_schemas import (
        BaseClassResourceDocument
    )


class InputFormat(str, Enum):
    """Define the supported input formats."""
    PDF = "pdf"
    GENERIC_TEXT = "generic_text"
    LATEX = "latex"
    MARKDOWN = "markdown"
    HTML = "html"


class MarkdownExtension(str, Enum):
    """Define the markdown extensions."""
    MARKDOWN = ".markdown"
    MD = ".md"
    MKD = ".mkd"
    MDWN = ".mdwn"
    MDOWN = ".mdown"
    MDTXT = ".mdtxt"
    MDTEXT = ".mdtext"
    TXT = ".text"


class LatexExtension(str, Enum):
    """Define the latex extensions."""
    TEX = ".tex"
    LATEX = ".latex"


class LoadingStrategy(str, Enum):
    """Define the loading strategies."""
    PyMuPDFLoader = "PyMuPDFLoader"
    UnstructuredMarkdownLoader = "UnstructuredMarkdownLoader"
    UnstructuredHTMLLoader = "UnstructuredHTMLLoader"

class SplitterStrategy(str, Enum):
    """Define the splitter strategies."""
    RecursiveCharacterTextSplitter = "RecursiveCharacterTextSplitter"
    LatexTextSplitter = "LatexTextSplitter"
    MarkdownTextSplitter = "MarkdownTextSplitter"


class InputDataIngestStrategy(str, Enum):
    """Define the input types."""
    S3_FILE_DOWNLOAD = "s3_file_download"
    URL_DOWNLOAD = "url_download"
    # WEB_CRAWL = "web_crawl"


LOADING_STRATEGY_MAPPING = {
    InputFormat.PDF: LoadingStrategy.PyMuPDFLoader,
    InputFormat.GENERIC_TEXT: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFormat.LATEX: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFormat.MARKDOWN: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFormat.HTML: LoadingStrategy.UnstructuredHTMLLoader,
}

SPLITTER_STRATEGY_MAPPING = {
    InputFormat.PDF: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFormat.GENERIC_TEXT: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFormat.LATEX: Language.LATEX,
    InputFormat.MARKDOWN: Language.MARKDOWN,
    InputFormat.HTML: Language.HTML,
}
TOTAL_PAGE_COUNT_STRINGS = ["total_pages", "total_page_count", "total_page_counts", "page_count"]
PAGE_NUMBER_STRINGS = ["page_number", "page_numbers", "page_num", "page_nums", "page"]


def get_splitter_text_splitter(input_format: InputFormat) -> TextSplitter:
    """Get the splitter strategy."""
    strategy_instructions = SPLITTER_STRATEGY_MAPPING.get(input_format)
    if strategy_instructions is None:
        raise ValueError("The input format is not supported.")
    if strategy_instructions in Language:
        return RecursiveCharacterTextSplitter()
    return getattr(text_splitter, strategy_instructions)()


def get_total_page_count(docs: list[Document]) -> Optional[int]:
    """Get the page count and total page count."""
    for doc in docs:
        for key in TOTAL_PAGE_COUNT_STRINGS:
            if key in doc.metadata:
                return doc.metadata[key]


def get_page_number(doc: Document) -> Optional[int]:
    """Get the page number."""
    for key in PAGE_NUMBER_STRINGS:
        if key in doc.metadata:
            return doc.metadata[key]


class InputDocument(BaseClassResourceDocument):
    """Define the input document."""
    input_data_ingest_strategy: InputDataIngestStrategy = Field(
        ...,
        description="The strategy for ingesting the input data.",
    )


class IngestedDocument(BaseClassResourceDocument):
    """Define the ingested document."""
    data_pointer: Any = Field(
        ...,
        description=("This field should 'point' to the data. This will mean different things "
            "depending on the input format and loading strategy. For example, if the input format "
            "is PDF and the loading strategy is PyMuPDF, then this field will be a path object, as another "
            "example, if the loading strategy is copy and paste, then this field will be a string."
        ),
    )
    input_format: InputFormat = Field(
        ...,
        description="The format of the input document.",
    )
    loading_strategy: LoadingStrategy = Field(
        ...,
        description="The loading strategy for the input document.",
    )

    @validator("loading_strategy")
    def verify_loading_strategy(cls, loading_strategy: LoadingStrategy, values: dict) -> LoadingStrategy:
        """Verify the loading strategy."""
        if values.get("input_format") is not None:
            assert loading_strategy == LOADING_STRATEGY_MAPPING[values.get("input_format")], "The loading strategy must match the input format."
        return loading_strategy


class Ingestor(ABC):
    """Define the ingestor class."""
    def ingest_data(self, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data."""
        raise NotImplementedError

    def _get_file_type(self, path: Path) -> str:
        """Get the file type."""
        def check_file_type(path: Path, extension_enum: Enum) -> bool:
            """Check if the file type matches given extensions."""
            return path.suffix in [extension.value for extension in extension_enum]
        def get_text_file_type(path: Path, file_contents: str) -> InputFormat:
            """Get the text file type."""
            if check_file_type(path, LatexExtension):
                return InputFormat.LATEX
            elif check_file_type(path, MarkdownExtension):
                return InputFormat.MARKDOWN
            elif bool(BeautifulSoup(file_contents, "html.parser").find()):
                return InputFormat.HTML
            return InputFormat.GENERIC_TEXT
        try:
            kind = filetype.guess(path)
            if kind:
                return InputFormat(kind.extension)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    return get_text_file_type(path, f.read())
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(traceback.format_exc())
            extension = kind.extension if kind else path.suffix
            raise ValueError(f"Unsupported file type: {extension}.") from e


class S3ObjectIngestor(Ingestor):
    """
    Define the S3 ingestor.

    This class is used for ingesting data from S3.
    """
    def ingest_data(self, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data from S3."""
        remote_file_url = input_data.full_resource_url
        s3 = boto3.resource("s3")
        bucket_name = remote_file_url.split("/")[2]
        key = "/".join(remote_file_url.split("/")[3:])
        bucket = s3.Bucket(bucket_name)
        tmp_path = Path(f"/tmp/{key}")
        bucket.download_file(key, str(tmp_path))
        document = IngestedDocument(
            data_pointer=tmp_path,
            input_format=self._get_file_type(tmp_path),
            loading_strategy=LOADING_STRATEGY_MAPPING[self._get_file_type(tmp_path)],
            **input_data.dict(),
        )
        return document


class URLIngestor(Ingestor):
    """
    Define the URL ingestor.

    This class is used for ingesting data from a URL.
    """
    def ingest_data(self, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data from a URL."""
        remote_file_url = input_data.full_resource_url
        tmp_path = Path(f"/tmp/{remote_file_url.split('/')[-1]}")
        r = requests.get(remote_file_url, timeout=5)
        if r.status_code != 200:
            raise ValueError(f"Could not download file from {remote_file_url}.")
        with open(tmp_path, "wb") as f:
            f.write(r.content)
        document = IngestedDocument(
            data_pointer=tmp_path,
            input_format=self._get_file_type(tmp_path),
            loading_strategy=LOADING_STRATEGY_MAPPING[self._get_file_type(tmp_path)],
            **input_data.dict(),
        )
        return document
