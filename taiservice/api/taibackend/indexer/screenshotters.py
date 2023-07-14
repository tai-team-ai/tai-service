"""Define the module with code to screenshot class resources."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from loguru import logger
from weasyprint import HTML as WeasyHTML


class ResourceUtility(ABC):
    """Define the interface for screen-shotting class resources."""
    @classmethod
    @abstractmethod
    def create_screenshots(
        cls,
        input_path: Path, 
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
            output_filename = f"{path.stem}_page_{i}.pdf"
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
        input_path: Path,
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        return cls._get_screenshot_from_pdf(input_path, start_page, last_page_to_include)

    @classmethod
    def split_resource(cls, input_path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """Split the resource into multiple resources."""
        return cls._get_pdf_pages_from_pdf(input_path, last_page_to_include)


class GenericText(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        input_path: Path, 
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class Latex(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        input_path: Path, 
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class Markdown(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        input_path: Path,
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        raise NotImplementedError(f"Screen-shotting method {cls.__class__.__name__} not implemented.")


class HTML(ResourceUtility):
    @classmethod
    def create_screenshots(
        cls,
        input_path: Path,
        start_page: Optional[int] = None,
        last_page_to_include: Optional[int] = None
    ) -> Optional[list[Path]]:
        """Create screenshots for all pages in the resource."""
        pdf_path = input_path.parent / f"{input_path.stem}.pdf"
        WeasyHTML(input_path).write_pdf(pdf_path)
        return cls._get_screenshot_from_pdf(pdf_path, start_page, last_page_to_include)

    @classmethod
    def split_resource(cls, input_path: Path, last_page_to_include: Optional[int] = None) -> Optional[list[Path]]:
        """Split the resource into multiple resources."""
        pdf_path = input_path.parent / f"{input_path.stem}.pdf"
        WeasyHTML(input_path).write_pdf(pdf_path)
        return cls._get_pdf_pages_from_pdf(pdf_path, last_page_to_include)


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
