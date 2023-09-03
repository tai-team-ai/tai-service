"""Define the module with code to screenshot class resources."""
import copy
from time import sleep
import os
import boto3
import shutil
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Optional, Sequence, Union
from uuid import uuid4
from pdf2image.pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from loguru import logger
import requests
from selenium import webdriver
from pydantic import HttpUrl

from taiservice.searchservice.backend.tai_search.data_ingestor_schema import IngestedDocument, InputFomat
from .data_ingestor_schema import IngestedDocument, BaseClassResourceDocument
from ..databases.document_db_schemas import ClassResourceDocument, ClassResourceProcessingStatus


def upload_file_to_s3(file_path: Union[str, Path], bucket_name: str, object_key: str) -> str:
    file_path = Path(file_path)
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucket_name)
    bucket.upload_file(str(file_path.resolve()), object_key)
    safe_object_key = urllib.parse.quote(object_key, safe="~()*!.'")
    return f"https://{bucket_name}.s3.amazonaws.com/{safe_object_key}"


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


class DocumentUtility(ABC):
    """Define the interface for screen-shotting class resources."""

    def __init__(self, thumbnail_bucket_name: str, ingested_doc: IngestedDocument):
        """Initialize the class."""
        self._thumbnail_bucket_name = thumbnail_bucket_name
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
        self._ingested_doc.preview_image_url = upload_file_to_s3(thumbnail_path, self._thumbnail_bucket_name, s3_key)

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        s3_key = get_s3_object_key(self._ingested_doc, self._ingested_doc.data_pointer.name)
        url = upload_file_to_s3(self._ingested_doc.data_pointer, self._thumbnail_bucket_name, s3_key)
        self._ingested_doc.full_resource_url = url


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
        self._ingested_doc.preview_image_url = upload_file_to_s3(thumbnail_path, self._thumbnail_bucket_name, s3_key)

    def upload_resource(self) -> None:
        """Upload the resource to the cloud and pass out a copy of the document with the cloud url."""
        if isinstance(self._ingested_doc.data_pointer, Path):
            url = upload_file_to_s3(self._ingested_doc.data_pointer, self._thumbnail_bucket_name, self._ingested_doc.data_pointer.name)
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
        for i, page in enumerate(input_pdf.pages):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(page)
            page_num = i + 1
            output_filepath = tmp_directory / f"{doc.data_pointer.stem}_page_{page_num}.pdf"
            with open(output_filepath, "wb") as out:
                pdf_writer.write(out)
            # TODO: we need to create a new Instance of a base class resource doc and then push to a queue
            output_doc = copy.deepcopy(doc)
            output_doc.id = uuid4()
            output_doc.data_pointer = output_filepath
            output_doc.metadata.page_number = page_num
            output_doc.metadata.total_page_count = len(input_pdf.pages)
            class_resource_doc.child_resource_ids.append(output_doc.id)
            output_docs.append(output_doc)
        return output_docs


def resource_utility_factory(bucket_name: str, ingested_doc: IngestedDocument) -> DocumentUtility:
    """Create the resource utility."""
    resource_utility_factory_mapping: dict[InputFomat, DocumentUtility] = {
        InputFomat.PDF: PDFDocumentUtility,
        InputFomat.HTML: HTMLDocumentUtility,
        InputFomat.YOUTUBE_VIDEO: YouTubeVideoDocumentUtility,
    }
    utility = resource_utility_factory_mapping.get(ingested_doc.input_format)
    if not utility:
        raise NotImplementedError(f"Could not find thumbnail generator for input format '{ingested_doc.input_format}'.")
    return utility(bucket_name, ingested_doc)


def resource_crawler_factory(ingested_doc: IngestedDocument) -> ResourceCrawler:
    """Create the resource crawler."""
    resource_crawler_factory_mapping = {
        InputFomat.PDF: PDFResourceCrawler,
    }
    resource_crawler = resource_crawler_factory_mapping.get(ingested_doc.input_format)
    if resource_crawler is None:
        raise NotImplementedError(f"Could not find resource crawler for input format '{ingested_doc.input_format}'.")
    return resource_crawler(ingested_doc)
