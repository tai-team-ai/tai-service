"""Define custom loaders for loading documents."""
from typing import Union
import re
import copy
from pathlib import Path
from langchain.document_loaders.base import BaseLoader
from langchain.document_loaders import (
    PyMuPDFLoader,
    MathpixPDFLoader,
    UnstructuredMarkdownLoader,
    BSHTMLLoader,
    YoutubeLoader,
)
from langchain.schema import Document
from loguru import logger
from .data_ingestor_schema import InputFormat, IngestedDocument
from taiservice.searchservice.runtime_settings import SearchServiceSettings


# we have chosen to use the BaseLoader as the parent class (instead of the
# langchain.document_loaders.pdf.BasePDFLoader) for our custom loader
# as we already ensure that the file has been downloaded using the Ingestor
# class. This means that we can assume that the file is available locally and
# we can use the file path to load the document.
class PDFLoader(BaseLoader):
    """Loader for PDF documents."""

    def __init__(self, pdf_path: Union[Path, str], **kwargs):
        """Initialize the loader."""
        path = Path(pdf_path)
        path = str(path.resolve())
        self.pdf_path = path
        self._pymu_pdf_loader = PyMuPDFLoader(path)
        self._math_pix_pdf_loader = MathpixPDFLoader(
            file_path=path,
            max_wait_time_seconds=900,
            processed_file_format="md",
            **kwargs,
        )


    def _clean_text(self, text: str) -> str:
        """Clean the text."""
        # replace all \\ with \
        return text.replace("\\\\", "\\")

    def _extract_links(self, text: str) -> list[str]:
        """Extract the links from the text."""
        links = re.findall(r"\[(.*?)\]\((.*?)\)", text)
        return [link[1] for link in links]

    def load(self) -> list[Document]:
        """Load PDF documents."""
        try:
            documents = self._math_pix_pdf_loader.load()
            for document in documents:
                document.page_content = self._clean_text(document.page_content)
                links = self._extract_links(document.page_content)
                document.metadata["links"] = links
            return documents
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.warning(f"Mathpix failed to load {self.pdf_path}. Falling back to PyMuPDF.")
            return self._pymu_pdf_loader.load()


LOADING_STRATEGY_MAPPING = {
    InputFormat.PDF: PDFLoader,
    InputFormat.GENERIC_TEXT: UnstructuredMarkdownLoader,
    InputFormat.LATEX: UnstructuredMarkdownLoader,
    InputFormat.MARKDOWN: UnstructuredMarkdownLoader,
    InputFormat.HTML: BSHTMLLoader,
    InputFormat.YOUTUBE_VIDEO: YoutubeLoader,
}


def loading_strategy_factory(ingested_doc: IngestedDocument) -> IngestedDocument:
    """Return a copy of the ingested document with the appropriate loader."""
    Loader = LOADING_STRATEGY_MAPPING.get(ingested_doc.input_format)
    runtime_settings = SearchServiceSettings()
    if not Loader:
        raise NotImplementedError(f"Loading strategy for {ingested_doc.input_format} not implemented.")
    if Loader == PDFLoader:
        secret = runtime_settings.mathpix_api_secret
        if secret:
            loader = Loader(ingested_doc.data_pointer, **secret.secret_value)
        else:
            loader = Loader(ingested_doc.data_pointer)
    else:
        loader = Loader(ingested_doc.data_pointer)
    copy_of_ingested_doc = copy.deepcopy(ingested_doc)
    copy_of_ingested_doc.loader = loader
    return copy_of_ingested_doc
