"""Define data ingestors used by the indexer."""
from typing import Optional
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
import traceback
import urllib.request
import filetype
from bs4 import BeautifulSoup
import tiktoken
from loguru import logger
import requests
from langchain.text_splitter import TextSplitter, RecursiveCharacterTextSplitter
from langchain import text_splitter
from langchain.schema import Document
# first imports are for local development, second imports are for deployment
try:
    from .data_ingestor_schema import (
        IngestedDocument,
        LatexExtension,
        MarkdownExtension,
        InputFormat,
        SPLITTER_STRATEGY_MAPPING,
        Language,
        TOTAL_PAGE_COUNT_STRINGS,
        PAGE_NUMBER_STRINGS,
        LOADING_STRATEGY_MAPPING,
    )
    from .data_ingestor_schema import InputDocument, InputFormat
except ImportError:
    from taibackend.indexer.data_ingestor_schema import (
        IngestedDocument,
        LatexExtension,
        MarkdownExtension,
        InputFormat,
        SPLITTER_STRATEGY_MAPPING,
        Language,
        TOTAL_PAGE_COUNT_STRINGS,
        PAGE_NUMBER_STRINGS,
        LOADING_STRATEGY_MAPPING,
    )
    from taibackend.indexer.indexer import InputDocument, InputFormat


def number_tokens(text: str) -> int:
    """Get the number of tokens in the text."""
    # the cl100k_base is the encoding for chat models
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(text))
    return num_tokens

def get_splitter_text_splitter(input_format: InputFormat) -> TextSplitter:
    """Get the splitter strategy."""
    strategy_instructions = SPLITTER_STRATEGY_MAPPING.get(input_format)
    kwargs = {
        'chunk_size': 250,
        'chunk_overlap': 50,
        'length_function': number_tokens,
    }
    if strategy_instructions is None:
        raise ValueError("The input format is not supported.")
    if strategy_instructions in Language:
        return RecursiveCharacterTextSplitter(**kwargs)
    splitter: TextSplitter = getattr(text_splitter, strategy_instructions)(**kwargs)
    return splitter


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

class Ingestor(ABC):
    """Define the ingestor class."""
    @classmethod
    @abstractmethod
    def ingest_data(cls, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data."""

    @staticmethod
    def _get_file_type(path: Path) -> InputFormat:
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
    @classmethod
    def ingest_data(cls, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data from S3."""
        tmp_path = Path(f"/tmp/{input_data.full_resource_url.split('/')[-1]}")
        response = requests.get(input_data.full_resource_url, timeout=10)
        response.raise_for_status() # Raise an error if the download fails
        with open(tmp_path, "wb") as f:
            f.write(response.content)
        file_type = cls._get_file_type(tmp_path)
        document = IngestedDocument(
            data_pointer=tmp_path,
            input_format=file_type,
            loading_strategy=LOADING_STRATEGY_MAPPING[cls._get_file_type(tmp_path)],
            **input_data.dict(),
        )
        return document

class URLIngestor(Ingestor):
    """
    Define the URL ingestor.

    This class is used for ingesting data from a URL.
    """
    @classmethod
    def ingest_data(cls, input_data: InputDocument) -> IngestedDocument:
        """Ingest the data from a URL."""
        remote_file_url = input_data.full_resource_url
        # remove the last slash if no charactesr follow it
        path = remote_file_url.path
        if path[-1] == "/":
            path = path[:-1]
        tmp_path = Path(f"/tmp/{path}.html")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(remote_file_url, tmp_path)
        document = IngestedDocument(
            data_pointer=tmp_path,
            input_format=cls._get_file_type(tmp_path),
            loading_strategy=LOADING_STRATEGY_MAPPING[cls._get_file_type(tmp_path)],
            **input_data.dict(),
        )
        return document
