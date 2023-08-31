"""Define the data ingestor schemas."""
from hashlib import sha1
from enum import Enum
from pathlib import Path
import re
from typing import Union
from pydantic import Field, root_validator, validator, HttpUrl
from langchain.text_splitter import Language
import requests
from ..shared_schemas import (
    BaseClassResourceDocument,
    StatefulClassResourceDocument,
)


class InputFomat(str, Enum):
    """Define the supported input formats."""

    PDF = "pdf"
    GENERIC_TEXT = "generic_text"
    LATEX = "latex"
    MARKDOWN = "markdown"
    HTML = "html"
    RAW_URL = "raw_url"
    YOUTUBE_VIDEO = "youtube_video"


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


# These loading strategies must match the corresponding class name in langchain
class LoadingStrategy(str, Enum):
    """Define the loading strategies."""

    PyMuPDFLoader = "PyMuPDFLoader"
    UnstructuredMarkdownLoader = "UnstructuredMarkdownLoader"
    BSHTMLLoader = "BSHTMLLoader"
    YoutubeLoader = "YoutubeLoader"


class SplitterStrategy(str, Enum):
    """Define the splitter strategies."""

    RecursiveCharacterTextSplitter = "RecursiveCharacterTextSplitter"
    LatexTextSplitter = "LatexTextSplitter"
    MarkdownTextSplitter = "MarkdownTextSplitter"


class InputDataIngestStrategy(str, Enum):
    """Define the input types."""

    S3_FILE_DOWNLOAD = "s3_file_download"
    URL_DOWNLOAD = "url_download"
    RAW_URL = "raw_url"
    # WEB_CRAWL = "web_crawl"


LOADING_STRATEGY_MAPPING = {
    InputFomat.PDF: LoadingStrategy.PyMuPDFLoader,
    InputFomat.GENERIC_TEXT: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFomat.LATEX: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFomat.MARKDOWN: LoadingStrategy.UnstructuredMarkdownLoader,
    InputFomat.HTML: LoadingStrategy.BSHTMLLoader,
    InputFomat.YOUTUBE_VIDEO: LoadingStrategy.YoutubeLoader,
}


SPLITTER_STRATEGY_MAPPING = {
    InputFomat.PDF: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFomat.GENERIC_TEXT: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFomat.LATEX: Language.LATEX,
    InputFomat.MARKDOWN: Language.MARKDOWN,
    InputFomat.HTML: Language.HTML,
    InputFomat.YOUTUBE_VIDEO: SplitterStrategy.RecursiveCharacterTextSplitter,
}
TOTAL_PAGE_COUNT_STRINGS = [
    "total_pages",
    "total_page_count",
    "total_page_counts",
    "page_count",
]
PAGE_NUMBER_STRINGS = ["page_number", "page_numbers", "page_num", "page_nums", "page"]


class InputDocument(BaseClassResourceDocument):
    """Define the input document."""

    input_data_ingest_strategy: InputDataIngestStrategy = Field(
        ...,
        description="The strategy for ingesting the input data.",
    )


class IngestedDocument(StatefulClassResourceDocument):
    """Define the ingested document."""

    data_pointer: Union[HttpUrl, str, Path] = Field(
        ...,
        description=(
            "This field should 'point' to the data. This will mean different things "
            "depending on the input format and loading strategy. For example, if the input format "
            "is PDF and the loading strategy is PyMuPDF, then this field will be a path object, as another "
            "example, if the loading strategy is copy and paste, then this field will be a string."
        ),
    )
    input_format: InputFomat = Field(
        ...,
        description="The format of the input document.",
    )
    loading_strategy: LoadingStrategy = Field(
        ...,
        description="The loading strategy for the input document.",
    )

    @root_validator(pre=True)
    def generate_hashed_content_id(cls, values: dict) -> dict:
        """Generate the hashed content id."""
        data_pointer = values.get("data_pointer")
        if isinstance(data_pointer, Path):
            hashed_document_contents = sha1(data_pointer.read_bytes()).hexdigest()
        elif isinstance(data_pointer, HttpUrl):
            url = data_pointer.split("?")[0]
            hashed_document_contents = sha1(url.encode()).hexdigest()
        elif isinstance(data_pointer, str):
            hashed_document_contents = sha1(data_pointer.encode()).hexdigest()
        else:
            raise ValueError("The data pointer must be a path, string, or url.")
        values["hashed_document_contents"] = hashed_document_contents
        return values

    @validator("loading_strategy")
    def verify_loading_strategy(cls, loading_strategy: LoadingStrategy, values: dict) -> LoadingStrategy:
        """Verify the loading strategy."""
        if values.get("input_format") is not None:
            assert (
                loading_strategy == LOADING_STRATEGY_MAPPING[values.get("input_format")]
            ), "The loading strategy must match the input format."
        return loading_strategy
