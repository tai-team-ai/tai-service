"""Define the module with code to screenshot class resources."""
import copy
from uuid import uuid4, UUID
from time import sleep
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Sequence, Union, Any
import urllib.parse
import boto3
from keybert import KeyBERT
from pdf2image.pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from loguru import logger
import requests
import fitz
from selenium import webdriver
from pydantic import HttpUrl
from taiservice.searchservice.backend.tai_search.data_ingestor_schema import IngestedDocument, InputFormat
from .data_ingestor_schema import IngestedDocument
from ..databases.document_db_schemas import ClassResourceDocument, ClassResourceChunkDocument


def upload_file_to_s3(file_path: Union[str, Path], bucket_name: str, object_key: str) -> str:
    file_path = Path(file_path)
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucket_name)
    bucket.upload_file(str(file_path.resolve()), object_key)
    safe_object_key = urllib.parse.quote(object_key, safe="~()*!.'")
    url = f"https://{bucket_name}.s3.amazonaws.com/{safe_object_key}"
    return url


def get_local_tmp_directory(doc: IngestedDocument, format: str) -> Path:
    """Get the local path to the thumbnail."""
    assert isinstance(doc.data_pointer, (Path, str)), f"Data pointer must be a path, not {type(doc.data_pointer)}"
    doc.data_pointer = Path(doc.data_pointer)
    path = Path("/tmp", str(doc.class_id), doc.hashed_document_contents, format)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_s3_object_key(doc: IngestedDocument, local_filename: str) -> str:
    """Get the s3 object key."""
    return f"class_id={doc.class_id}/document_hash={doc.hashed_document_contents}/{local_filename}"

def get_s3_key_for_chunk(chunk_id: UUID, doc: IngestedDocument, local_filename: str) -> str:
    """This function is supposed to get an s3_key for a chunk."""
    return f"class_id={doc.class_id}/document_hash={doc.hashed_document_contents}/chunk_id={chunk_id}/{local_filename}"


class DocumentUtility(ABC):
    """Define the interface for screen-shotting class resources."""

    def __init__(self, bucket_name: str, ingested_doc: IngestedDocument):
        """Initialize the class."""
        self._bucket_name = bucket_name
        self._ingested_doc = copy.deepcopy(ingested_doc)

    @property
    def ingested_doc(self) -> IngestedDocument:
        """Return the ingested document."""
        return self._ingested_doc

    @abstractmethod
    def create_thumbnail(self) -> None:
        """
        Create a thumbnail for the document.

        IMPORTANT: After creating the thumbnail, the document must be updated with the
        thumbnail url so that the thumbnail is accessible from the document.
        """

    @abstractmethod
    def upload_resource(self) -> None:
        """
        Upload the resource to the cloud.

        IMPORTANT: After uploading the resource, the document must be updated with the
        resource url so that the resource is accessible from the document.
        """

    @abstractmethod
    def augment_chunks(self, chunk_docs: list[ClassResourceChunkDocument]) -> list[ClassResourceChunkDocument]:
        """
        Augment the chunk documents.

        An example of this, could be creating a copy of the pdf page and highlighting it or
        for a youtube video, adding a timestamp to the url.
        """


class PDFDocumentUtility(DocumentUtility):
    """Implement the PDF Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        thumbnail_format = "png"
        thumbnail_directory = get_local_tmp_directory(self._ingested_doc, thumbnail_format)
        thumbnail_filename = f"{self._ingested_doc.metadata.title}-thumbnail.{thumbnail_format}"
        thumbnail_path = thumbnail_directory / thumbnail_filename
        if thumbnail_path.exists():
            pass
        else:
            convert_from_path(
                self._ingested_doc.data_pointer,
                fmt=thumbnail_format,
                output_folder=thumbnail_directory,
                output_file=thumbnail_path.stem,
                first_page=0,
                last_page=1,
                dpi=84,  # roughly HD resolution
            )
            thumbnail_path = list(thumbnail_path.parent.glob(f"{thumbnail_path.stem}*"))[0]
            new_path = thumbnail_path.parent / thumbnail_filename
            thumbnail_path.rename(new_path)
            thumbnail_path = new_path
        s3_key = get_s3_object_key(self._ingested_doc, thumbnail_path.name)
        self._ingested_doc.preview_image_url = upload_file_to_s3(thumbnail_path, self._bucket_name, s3_key)

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        s3_key = get_s3_object_key(self._ingested_doc, self._ingested_doc.data_pointer.name)
        url = upload_file_to_s3(self._ingested_doc.data_pointer, self._bucket_name, s3_key)
        self._ingested_doc.full_resource_url = url

    def highlight_section_in_pdf(self, pdf_path: Union[str, Path], chunk_keywords: list[str]) -> Path:
        """Make a highlighted copy of a specific section in a pdf."""
        path = Path(pdf_path)
        pdf_file = fitz.open(str(path.resolve()))
        pdf_page_count = pdf_file.page_count   #var to hold page count
        keywords = set([keyword.lower() for keyword in chunk_keywords])
        for page in range(pdf_page_count):
            page_obj = pdf_file[page]
            content_of_page = page_obj.get_text("words", sort=False)
            for word in content_of_page:
                if word[4].lower() in keywords:
                    rect_comp = fitz.Rect(word[:4])
                    page_obj.add_highlight_annot(rect_comp)
        output_path = path.parent / f"highlighted_{path.name}"
        pdf_file.save(str(output_path.resolve()), garbage=4, deflate=True, clean=True)
        pdf_file.close()
        return output_path

    def augment_chunks(self, chunk_docs: list[ClassResourceChunkDocument]) -> list[ClassResourceChunkDocument]:
        assert isinstance(self._ingested_doc.data_pointer, Path), f"Data pointer must be a path, not {type(self._ingested_doc.data_pointer)}"
        for chunk in chunk_docs:
            # copy the pdf to a new file with the same as teh data poitner with a file name of chunk_id=chunk_id.pdf
            new_file_path = self._ingested_doc.data_pointer.parent / f"chunk_id={chunk.id}.pdf"
            # copy to new file path
            shutil.copy(self._ingested_doc.data_pointer, new_file_path)
            keyword_score_pairs: tuple[str, float] = KeyBERT().extract_keywords(chunk.chunk, top_n=20, keyphrase_ngram_range=(1, 1), stop_words="english")
            keywords = [keyword for keyword, _ in keyword_score_pairs]
            path = self.highlight_section_in_pdf(new_file_path, keywords)
            s3_key = get_s3_key_for_chunk(chunk.id, self._ingested_doc, path.name)
            chunk.raw_chunk_url = upload_file_to_s3(path, self._bucket_name, s3_key)
        return chunk_docs


class HTMLDocumentUtility(DocumentUtility):
    """Implement the HTML Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        thumbnail_format = "png"
        thumbnail_directory = get_local_tmp_directory(self._ingested_doc, thumbnail_format)
        thumbnail_path = thumbnail_directory / f"thumbnail.{thumbnail_format}"
        doc = self._ingested_doc
        if thumbnail_path.exists():
            pass
        else:
            options = webdriver.ChromeOptions()
            options.headless = True
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=768,1024")
            driver = webdriver.Chrome(options=options)
            if isinstance(doc.data_pointer, Path):
                doc.data_pointer = f"file://{doc.data_pointer.absolute()}"
            driver.get(doc.data_pointer)
            sleep(5)
            driver.get_screenshot_as_file(thumbnail_path)
            driver.close()
        s3_key = get_s3_object_key(self._ingested_doc, thumbnail_path.name)
        self._ingested_doc.preview_image_url = upload_file_to_s3(thumbnail_path, self._bucket_name, s3_key)

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        if isinstance(self._ingested_doc.data_pointer, Path):
            url = upload_file_to_s3(
                self._ingested_doc.data_pointer, self._bucket_name, self._ingested_doc.data_pointer.name
            )
        elif isinstance(self._ingested_doc.data_pointer, HttpUrl):
            url = str(self._ingested_doc.data_pointer)
        else:
            raise ValueError(f"Data pointer must be a path or url, not {type(self._ingested_doc.data_pointer)}")
        self._ingested_doc.full_resource_url = url


class YouTubeVideoDocumentUtility(DocumentUtility):
    """Implement the YouTube Video Document Utility."""

    def create_thumbnail(self) -> None:
        video_id = self._ingested_doc.data_pointer
        # urls ranked by quality ascending
        urls = [
            f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        ]
        self._ingested_doc.preview_image_url = urls[0]
        for url in urls:
            response = requests.get(url, timeout=4)
            if response.status_code == 200:
                self._ingested_doc.preview_image_url = url
                break

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        self._ingested_doc.full_resource_url = f"https://www.youtube.com/watch?v={self._ingested_doc.data_pointer}"


class GenericTextDocumentUtility(DocumentUtility):
    """Implement the Generic Text Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        raise NotImplementedError(f"Uploading method {self.__class__.__name__} not implemented.")


class LatexDocumentUtility(DocumentUtility):
    """Implement the Latex Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        raise NotImplementedError(f"Uploading method {self.__class__.__name__} not implemented.")


class MarkdownDocumentUtility(DocumentUtility):
    """Implement the Markdown Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        raise NotImplementedError(f"Uploading method {self.__class__.__name__} not implemented.")


class RawURLDocumentUtility(DocumentUtility):
    """Implement the Raw URL Document Utility."""

    def create_thumbnail(self) -> None:
        """Create a thumbnail for the document and pass out a copy of the document with the thumbnail."""
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        raise NotImplementedError(f"Uploading method {self.__class__.__name__} not implemented.")


class ResourceCrawler(ABC):
    """Define the interface for crawling class resources."""

    def __init__(self, ingested_doc: IngestedDocument):
        """Initialize the class."""
        self._ingested_doc = copy.deepcopy(ingested_doc)
        self._class_resource_doc: Optional[ClassResourceDocument] = None

    def _get_base_ingested_doc(self) -> IngestedDocument:
        """Get the base ingested doc."""
        output_doc = copy.deepcopy(self._ingested_doc)
        output_doc.id = uuid4()
        return output_doc

    @abstractmethod
    def crawl(
        self, class_resource_doc: ClassResourceDocument
    ) -> Sequence[IngestedDocument]:  # TODO: change to BaseClassResourceDocument
        """
        Crawl the resource and return a list of discovered resources.

        Any class that implements this method must return a list of documents that are
        created by crawling the resource. For a PDF, this could mean finding all pages,
        following links, etc. For a website, this could mean following links, to other pages,
        getting videos, etc.

        IMPORTANT: After crawling, the class resource document originally passed into the
        method must be updated with the child resource IDs that were discovered so that
        there is a reference to the child resources.
        """


class DefaultCrawler(ResourceCrawler):
    """Implement the default crawler."""

    def crawl(
        self, class_resource_doc: ClassResourceDocument
    ) -> Sequence[IngestedDocument]:  # TODO: change to BaseClassResourceDocument
        """
        Crawl the resource and return a list of discovered resources.

        This generic default crawler will create one parent doc and one child (which in this
        case will be the same as the parent doc)
        """
        output_doc = self._get_base_ingested_doc()
        class_resource_doc.child_resource_ids.append(output_doc.id)
        return [output_doc]


class PDFResourceCrawler(ResourceCrawler):
    """Implement the PDF resource crawler."""

    def crawl(
        self, class_resource_doc: ClassResourceDocument
    ) -> Sequence[IngestedDocument]:  # TODO: change to BaseClassResourceDocument
        """
        Crawl the resource and return a list of discovered resources.

        For right now for pdfs, crawling just means to split the pdf into multiple pdfs of 1 page each.
        by page.
        """
        doc = self._ingested_doc
        assert isinstance(doc.data_pointer, (str, Path)), f"Data pointer must be a path, not {type(doc.data_pointer)}"
        doc.data_pointer = Path(doc.data_pointer)
        input_pdf = PdfReader(open(doc.data_pointer, "rb"))
        tmp_directory = get_local_tmp_directory(doc, "pdf")

        output_docs: list[IngestedDocument] = []
        for page_num, page in enumerate(input_pdf.pages, 1):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(page)
            output_filepath = tmp_directory / f"{doc.data_pointer.stem}_page_{page_num}.pdf"
            with open(output_filepath, "wb") as out:
                pdf_writer.write(out)
            # TODO: we need to create a new Instance of a base class resource doc and then push to a queue
            output_doc = self._get_base_ingested_doc()
            output_doc.data_pointer = output_filepath
            output_doc.metadata.page_number = page_num
            output_doc.metadata.total_page_count = len(input_pdf.pages)
            class_resource_doc.child_resource_ids.append(output_doc.id)
            output_docs.append(output_doc)
        return output_docs


def resource_utility_factory(bucket_name: str, ingested_doc: IngestedDocument) -> DocumentUtility:
    """Create the resource utility."""
    resource_utility_factory_mapping: dict[InputFormat, Any] = {
        InputFormat.PDF: PDFDocumentUtility,
        InputFormat.HTML: HTMLDocumentUtility,
        InputFormat.YOUTUBE_VIDEO: YouTubeVideoDocumentUtility,
    }
    Utility = resource_utility_factory_mapping.get(ingested_doc.input_format)
    if not Utility:
        raise NotImplementedError(f"Could not find thumbnail generator for input format '{ingested_doc.input_format}'.")
    return Utility(bucket_name, ingested_doc)


def resource_crawler_factory(ingested_doc: IngestedDocument) -> ResourceCrawler:
    """Create the resource crawler."""
    resource_crawler_factory_mapping = {
        InputFormat.PDF: PDFResourceCrawler,
    }
    resource_crawler = resource_crawler_factory_mapping.get(ingested_doc.input_format, DefaultCrawler)
    return resource_crawler(ingested_doc)
