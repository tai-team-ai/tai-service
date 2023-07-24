"""Define the data ingestor schemas."""
from hashlib import sha1
from enum import Enum
from pathlib import Path
import re
from typing import Union
from pydantic import Field, root_validator, validator, HttpUrl
from langchain.text_splitter import Language
import requests
# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import (
        BaseClassResourceDocument,
        StatefulClassResourceDocument
    )
except ImportError:
    from taibackend.shared_schemas import (
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
    BSHTMLLoader = "BSHTMLLoader"

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
    InputFormat.HTML: LoadingStrategy.BSHTMLLoader,
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


class InputDocument(BaseClassResourceDocument):
    """Define the input document."""
    input_data_ingest_strategy: InputDataIngestStrategy = Field(
        ...,
        description="The strategy for ingesting the input data.",
    )

    @root_validator(pre=True)
    def set_input_data_ingest_strategy(cls, values: dict) -> dict:
        """Set the input data ingest strategy."""
        url_field_name = "full_resource_url"
        url: HttpUrl = values.get(url_field_name)
        values["input_data_ingest_strategy"] = InputDataIngestStrategy.URL_DOWNLOAD
        if url.startswith("s3://"):
            _, bucket_domain_name, *path = url.split("/")
            values[url_field_name] = f"https://{bucket_domain_name}/{'/'.join(path)}"
            values["input_data_ingest_strategy"] = InputDataIngestStrategy.S3_FILE_DOWNLOAD
        elif re.match(r"https://.*\.s3\.amazonaws\.com/.*", url):
            values["input_data_ingest_strategy"] = InputDataIngestStrategy.S3_FILE_DOWNLOAD
        return values


class IngestedDocument(StatefulClassResourceDocument):
    """Define the ingested document."""
    data_pointer: Union[Path, str, HttpUrl] = Field(
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

    @root_validator(pre=True)
    def generate_hashed_content_id(cls, values: dict) -> dict:
        """Generate the hashed content id."""
        data_pointer = values.get("data_pointer")
        if isinstance(data_pointer, Path):
            hashed_document_contents = sha1(data_pointer.read_bytes()).hexdigest()
        elif isinstance(data_pointer, str):
            hashed_document_contents = sha1(data_pointer.encode()).hexdigest()
        elif isinstance(data_pointer, HttpUrl):
            response = requests.get(data_pointer, timeout=10)
            assert response.status_code == 200, "Could not get the data from the url."
            hashed_document_contents = sha1(response.content).hexdigest()
        else:
            raise ValueError("The data pointer must be a path, string, or url.")
        values["hashed_document_contents"] = hashed_document_contents
        return values


    @validator("loading_strategy")
    def verify_loading_strategy(cls, loading_strategy: LoadingStrategy, values: dict) -> LoadingStrategy:
        """Verify the loading strategy."""
        if values.get("input_format") is not None:
            assert loading_strategy == LOADING_STRATEGY_MAPPING[values.get("input_format")], "The loading strategy must match the input format."
        return loading_strategy


