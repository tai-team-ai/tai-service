"""Define data ingestors used by the tai_search."""
from typing import Optional, Type
from abc import ABC, abstractmethod
from uuid import uuid4
from enum import Enum
from pathlib import Path
import traceback
import urllib.request
import urllib.parse
import filetype
from bs4 import BeautifulSoup
import tiktoken
from loguru import logger
import requests
from langchain.text_splitter import TextSplitter, RecursiveCharacterTextSplitter
from langchain import text_splitter
from langchain.schema import Document
from langchain.document_loaders.youtube import (
    ALLOWED_NETLOCK as YOUTUBE_NETLOCS,
    YoutubeLoader,
)
from .data_ingestor_schema import (
    IngestedDocument,
    LatexExtension,
    MarkdownExtension,
    SPLITTER_STRATEGY_MAPPING,
    Language,
    TOTAL_PAGE_COUNT_STRINGS,
    PAGE_NUMBER_STRINGS,
    InputDocument,
    InputFormat,
)
from ..shared_schemas import ChunkSize


def number_tokens(text: str) -> int:
    """Get the number of tokens in the text."""
    # the cl100k_base is the encoding for chat models
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(text))
    return num_tokens


CHUNK_SIZE_TO_CHAR_COUNT_MAPPING = {
    ChunkSize.SMALL: 500,
    ChunkSize.LARGE: 2000,
}
OVERLAP_SIZE_TO_CHAR_COUNT_MAPPING = {
    ChunkSize.SMALL: 100,
    ChunkSize.LARGE: 300,
}


def get_text_splitter(input_format: InputFormat, chunk_size: ChunkSize) -> TextSplitter:
    """Get the splitter strategy."""
    strategy_instructions = SPLITTER_STRATEGY_MAPPING.get(input_format)
    kwargs = {
        "chunk_size": CHUNK_SIZE_TO_CHAR_COUNT_MAPPING[chunk_size],
        "chunk_overlap": OVERLAP_SIZE_TO_CHAR_COUNT_MAPPING[chunk_size],
    }
    if strategy_instructions is None:
        raise ValueError("The input format is not supported.")
    if strategy_instructions in Language:
        return RecursiveCharacterTextSplitter.from_language(language=strategy_instructions, **kwargs)
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
    def ingest_data(cls, input_data: InputDocument, bucket_name: str) -> IngestedDocument:
        """Ingest the data."""

    @staticmethod
    def _get_input_format(input_pointer: str) -> InputFormat:
        """Get the file type."""

        def check_file_type(path: Path, extension_enum: Type[Enum]) -> bool:
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

        def get_url_type(url: str) -> InputFormat:
            parsed_url = urllib.parse.urlparse(url)
            netloc = parsed_url.netloc
            path = parsed_url.path
            if netloc in YOUTUBE_NETLOCS and path.startswith("/watch"):
                return InputFormat.YOUTUBE_VIDEO
            else:
                raise ValueError(f"Unsupported url type: {url}")

        try:
            return get_url_type(input_pointer)
        except ValueError as e:
            logger.info(f"Failed to get url type: {e}, retrying with file type.")
        try:
            path = Path(input_pointer)
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

    @classmethod
    def _download_from_url(cls, input_data: InputDocument) -> IngestedDocument:
        # get just the last part of the path without the query param
        final_path = urllib.parse.urlparse(input_data.full_resource_url).path.split("/")[-1]
        tmp_path: Path = Path("/tmp") / str(uuid4()) / final_path
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(input_data.full_resource_url, timeout=10)
        response.raise_for_status()  # Raise an error if the download fails
        with open(tmp_path, "wb") as f:
            f.write(response.content)
        file_type = cls._get_input_format(str(tmp_path.resolve()))
        document = IngestedDocument(
            data_pointer=tmp_path,
            input_format=file_type,
            **input_data.dict(),
        )
        return document


class S3ObjectIngestor(Ingestor):
    """
    Define the S3 ingestor.

    This class is used for ingesting data from S3.
    """

    @classmethod
    def ingest_data(cls, input_data: InputDocument, bucket_name: str) -> IngestedDocument:
        """Ingest the data from S3."""
        # TODO: add s3 signature
        return cls._download_from_url(input_data)


class WebPageIngestor(Ingestor):
    """
    Define the URL ingestor.

    This class is used for ingesting data from a URL.
    """

    @classmethod
    def ingest_data(cls, input_data: InputDocument, bucket_name: str) -> IngestedDocument:
        """Ingest the data from a URL."""
        doc = cls._download_from_url(input_data)
        return doc


class RawUrlIngestor(Ingestor):
    """
    Define the raw URL ingestor.

    This class is used for ingesting data from a raw URL.
    """

    @staticmethod
    def is_raw_url(url: str) -> bool:
        """Check if the url is a raw url."""
        parsed_url = urllib.parse.urlparse(url)
        netloc = parsed_url.netloc
        if netloc in YOUTUBE_NETLOCS:
            return True
        return False

    @classmethod
    def ingest_data(cls, input_data: InputDocument, bucket_name: str) -> IngestedDocument:
        """Ingest the data from a raw URL."""
        url_type = cls._get_input_format(str(input_data.full_resource_url))
        if url_type == InputFormat.YOUTUBE_VIDEO:
            data_pointer = YoutubeLoader.extract_video_id(input_data.full_resource_url)
        else:
            data_pointer = input_data.full_resource_url
        document = IngestedDocument(
            data_pointer=data_pointer,
            input_format=url_type,
            **input_data.dict(),
        )
        return document
