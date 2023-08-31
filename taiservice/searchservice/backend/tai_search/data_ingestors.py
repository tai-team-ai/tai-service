"""Define data ingestors used by the tai_search."""
from typing import Callable, Optional, Union, Any
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
import boto3
from pydantic import HttpUrl
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
    LOADING_STRATEGY_MAPPING,
    InputDocument,
    InputFomat,
    InputDataIngestStrategy,
)
from .resource_utilities import ResourceUtility, PDF, HTML
from ..databases.document_db_schemas import ClassResourceChunkDocument
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


def get_text_splitter(input_format: InputFomat, chunk_size: ChunkSize) -> TextSplitter:
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
    def _get_object_prefix(ingested_doc: IngestedDocument) -> str:
        """Get the object prefix."""
        class_id = f"class_id={ingested_doc.class_id}"
        resource_id = f"resource_id={ingested_doc.id_as_str}"
        return f"{class_id}/{resource_id}/"

    @staticmethod
    def _screenshot_resource(
        data_pointer: Union[HttpUrl, Path],
        input_format: InputFomat,
        first_page_only: bool = True,
    ) -> list[Path]:
        screenshot_strategy_mapping: dict[InputFomat, ResourceUtility] = {
            InputFomat.HTML: HTML,
            InputFomat.PDF: PDF,
        }
        resource_utility = screenshot_strategy_mapping[input_format]
        last_page_to_screenshot = 1 if first_page_only else None
        return resource_utility.create_screenshots(data_pointer, last_page_to_include=last_page_to_screenshot)

    @staticmethod
    def _upload_to_cold_store(file_paths: list[Path], object_keys: list[str], bucket_name: str) -> Union[list[HttpUrl], HttpUrl]:
        """Put the ingested document to s3."""
        is_length_one = len(file_paths) == 1
        try:
            s3 = boto3.resource("s3")
            bucket = s3.Bucket(bucket_name)
            urls = []
            for filepath, object_key in zip(file_paths, object_keys):
                bucket.upload_file(str(filepath.resolve()), object_key)
                urls.append(f"""https://{bucket_name}.s3.amazonaws.com/{urllib.parse.quote(object_key, safe="~()*!.'")}""")
            return urls[0] if is_length_one else urls
        except Exception as e:  # pylint: disable=broad-except
            logger.critical(f"Failed to upload to s3: {e}")
            raise RuntimeError(f"Failed to upload to s3: {e}") from e

    @staticmethod
    def run_screenshot_op(func: Callable, *args, **kwargs) -> Any:
        """Run the screenshot operation."""
        try:
            return func(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"Failed to create screenshots: {e}")
            logger.warning(traceback.format_exc())
            logger.warning("Skipping screenshot upload")
            return []

    @staticmethod
    def run_split_resource_op(func: Callable, *args, **kwargs) -> list[Path]:
        """Run the split resource operation."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError(f"Failed to split resource: {e}") from e

    @classmethod
    def upload_document_to_cold_store(
        cls,
        bucket_name: str,
        ingested_doc: IngestedDocument,
        chunks: list[ClassResourceChunkDocument],
    ) -> None:
        """Put the ingested document to s3."""
        object_prefix = cls._get_object_prefix(ingested_doc)
        screenshot_urls, split_resource_urls = [], []

        def screenshot_upload_resource() -> Union[list[HttpUrl], HttpUrl]:
            screenshot_paths = cls._screenshot_resource(
                ingested_doc.data_pointer,
                ingested_doc.input_format,
                first_page_only=False,
            )
            screenshot_object_keys = [f"{object_prefix}{i + 1}/{path.name}" for i, path in enumerate(screenshot_paths)]
            return cls._upload_to_cold_store(screenshot_paths, screenshot_object_keys, bucket_name)

        def split_and_upload_pdf() -> Union[list[HttpUrl], HttpUrl]:
            split_resource_paths = PDF.split_resource(input_path=ingested_doc.data_pointer)
            split_objects_keys = [f"{object_prefix}{i +  1}/{path.name}" for i, path in enumerate(split_resource_paths)]
            return cls._upload_to_cold_store(split_resource_paths, split_objects_keys, bucket_name)
        # TODO need to screenshot youtube videos, and create snippet urls for youtube videos with timestamps
        screenshot_urls = cls.run_screenshot_op(screenshot_upload_resource)
        if isinstance(screenshot_urls, str) and ingested_doc.input_format != InputFomat.HTML:
            screenshot_urls = [screenshot_urls]
        if ingested_doc.input_format == InputFomat.PDF:
            split_resource_urls = cls.run_split_resource_op(split_and_upload_pdf)
            if isinstance(split_resource_urls, str):
                split_resource_urls = [split_resource_urls]
            for chunk in chunks:
                chunk.raw_chunk_url = split_resource_urls[chunk.metadata.page_number] if split_resource_urls else None
                chunk.preview_image_url = screenshot_urls[chunk.metadata.page_number] if screenshot_urls else None
                chunk.metadata.title = f"{chunk.metadata.title} (Page {chunk.metadata.page_number + 1})"
            return
        for chunk in chunks:
            chunk.raw_chunk_url = ingested_doc.full_resource_url
            chunk.preview_image_url = screenshot_urls if screenshot_urls else None

    @classmethod
    def _upload_resource_to_cold_store_and_update_ingested_doc(
        cls,
        bucket_name: str,
        input_doc: InputDocument,
        ingested_doc: IngestedDocument,
    ) -> None:
        """Put the ingested document to s3."""
        object_prefix = cls._get_object_prefix(ingested_doc)
        is_webpage_html = (
            ingested_doc.input_format == InputFomat.HTML
            and input_doc.input_data_ingest_strategy == InputDataIngestStrategy.URL_DOWNLOAD
        )

        def screenshot_resource() -> None:
            if is_webpage_html:
                data_pointer = input_doc.full_resource_url
            else:
                data_pointer = ingested_doc.data_pointer
            screenshot_path = Ingestor._screenshot_resource(data_pointer, ingested_doc.input_format)[0]
            screenshot_object_key = f"{object_prefix}{screenshot_path.name}"
            ingested_doc.preview_image_url = cls._upload_to_cold_store([screenshot_path], [screenshot_object_key], bucket_name)

        def upload_raw_resource_to_cold_store() -> None:
            if not is_webpage_html:
                ingested_doc.full_resource_url = cls._upload_to_cold_store(
                    [ingested_doc.data_pointer],
                    [f"{object_prefix}{ingested_doc.data_pointer.name}"],
                    bucket_name,
                )

        cls.run_screenshot_op(screenshot_resource)
        cls.run_split_resource_op(upload_raw_resource_to_cold_store)

    @staticmethod
    def _get_input_format(input_pointer: str) -> InputFomat:
        """Get the file type."""

        def check_file_type(path: Path, extension_enum: Enum) -> bool:
            """Check if the file type matches given extensions."""
            return path.suffix in [extension.value for extension in extension_enum]

        def get_text_file_type(path: Path, file_contents: str) -> InputFomat:
            """Get the text file type."""
            if check_file_type(path, LatexExtension):
                return InputFomat.LATEX
            elif check_file_type(path, MarkdownExtension):
                return InputFomat.MARKDOWN
            elif bool(BeautifulSoup(file_contents, "html.parser").find()):
                return InputFomat.HTML
            return InputFomat.GENERIC_TEXT

        def get_url_type(url: str) -> InputFomat:
            parsed_url = urllib.parse.urlparse(url)
            netloc = parsed_url.netloc
            path = parsed_url.path
            if netloc in YOUTUBE_NETLOCS and path.startswith("/watch"):
                return InputFomat.YOUTUBE_VIDEO
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
                return InputFomat(kind.extension)
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
            loading_strategy=LOADING_STRATEGY_MAPPING[file_type],
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
        # sign if needed to dowload from private bucket
        doc = cls._download_from_url(input_data)
        cls._upload_resource_to_cold_store_and_update_ingested_doc(
            bucket_name=bucket_name,
            input_doc=input_data,
            ingested_doc=doc,
        )
        return doc


class WebPageIngestor(Ingestor):
    """
    Define the URL ingestor.

    This class is used for ingesting data from a URL.
    """

    @classmethod
    def ingest_data(cls, input_data: InputDocument, bucket_name: str) -> IngestedDocument:
        """Ingest the data from a URL."""
        doc = cls._download_from_url(input_data)
        cls._upload_resource_to_cold_store_and_update_ingested_doc(
            bucket_name=bucket_name,
            input_doc=input_data,
            ingested_doc=doc,
        )
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
        if url_type == InputFomat.YOUTUBE_VIDEO:
            data_pointer = YoutubeLoader.extract_video_id(input_data.full_resource_url)
        else:
            data_pointer = input_data.full_resource_url
        document = IngestedDocument(
            data_pointer=data_pointer,
            input_format=url_type,
            loading_strategy=LOADING_STRATEGY_MAPPING[url_type],
            **input_data.dict(),
        )
        return document
