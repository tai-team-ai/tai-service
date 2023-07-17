"""Define the module with code to screenshot class resources."""
from time import sleep
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from loguru import logger
from selenium import webdriver
from pydantic import HttpUrl


class ResourceUtility(ABC):
    """Define the interface for screen-shotting class resources."""
    @classmethod
    @abstractmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""

    @classmethod
    @abstractmethod
    def split_resource(cls, input_path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """Split the resource into multiple resources."""

    @staticmethod
    def _get_pdf_pages_from_pdf(path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """Get the pages of a PDF."""
        pages = []
        input_pdf = PdfReader(open(path, "rb"))
        num_pages = len(input_pdf.pages)
        last_page_to_include = min(last_page_to_include, num_pages) if last_page_to_include else num_pages
        for i in range(last_page_to_include):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(input_pdf.pages[i])
            output_filename = f"{str(path.resolve())}_page_{i}.pdf"
            with open(output_filename, "wb") as out:
                pdf_writer.write(out)
            pages.append(Path(output_filename))
        if len(pages) > 0:
            return pages
        logger.warning(f"Could not get pages from PDF {path}")

    @staticmethod
    def _get_screenshot_from_pdf(
        path: Path,
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Get the screenshot from a PDF."""
        images = convert_from_path(path, first_page=start_page, last_page=last_page_to_include)
        paths = []
        for i, image in enumerate(images):
            save_path = path.parent / f"{path.stem}_{i}.png"
            paths.append(save_path)
            image.save(save_path, format='png')
        if len(paths) > 0:
            return paths
        logger.warning(f"Could not get screenshot from PDF {path}")

class PDF(ResourceUtility):
    """Define the PDF screenshotter."""
    @classmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        assert isinstance(data_pointer, Path), f"Data pointer must be a path, not {type(data_pointer)}"
        return cls._get_screenshot_from_pdf(data_pointer, start_page, last_page_to_include)

    @classmethod
    def split_resource(cls, input_path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """Split the resource into multiple resources."""
        return cls._get_pdf_pages_from_pdf(input_path, last_page_to_include)


class GenericText(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class Latex(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class Markdown(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class HTML(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        data_pointer: Union[Path, HttpUrl],
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        options = webdriver.ChromeOptions()
        options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=768,1024")
        driver = webdriver.Chrome(options=options)
        output_path = data_pointer.parent / f"{data_pointer.stem}.png"
        if isinstance(data_pointer, Path):
            data_pointer = f"file://{data_pointer.absolute()}"
        driver.get(data_pointer)
        sleep(5)
        driver.get_screenshot_as_file(output_path)
        driver.close()
        return [output_path]

    @classmethod
    def split_resource(cls, input_path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """
        Split the resource into multiple resources.

        This is not implemented for HTML files, as they are not paginated.
        """
        return [input_path]


class RawURL(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        input_path: Path,
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")
