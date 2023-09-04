"""Define the data ingestor schemas."""
from enum import Enum
from typing import Optional, Type
from pydantic import Field, validator
from langchain.text_splitter import Language
from langchain.document_loaders.base import BaseLoader
from ..shared_schemas import (
    BaseClassResourceDocument,
    StatefulClassResourceDocument,
)


class InputFormat(str, Enum):
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


SPLITTER_STRATEGY_MAPPING = {
    InputFormat.PDF: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFormat.GENERIC_TEXT: SplitterStrategy.RecursiveCharacterTextSplitter,
    InputFormat.LATEX: Language.LATEX,
    InputFormat.MARKDOWN: Language.MARKDOWN,
    InputFormat.HTML: Language.HTML,
    InputFormat.YOUTUBE_VIDEO: SplitterStrategy.RecursiveCharacterTextSplitter,
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

    input_format: InputFormat = Field(
        ...,
        description="The format of the input document.",
    )

    loader: Optional[BaseLoader] = Field(
        default=None,
        description="The loader for the input document.",
    )
