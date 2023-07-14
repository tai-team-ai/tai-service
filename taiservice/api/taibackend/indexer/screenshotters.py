"""Define the module with code to screenshot class resources."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from pdf2image import convert_from_path
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .data_ingestors import IngestedDocument
except ImportError:
    from taibackend.indexer.data_ingestors import IngestedDocument


class ResourceScreenshotter(ABC):
    """Define the interface for screen-shotting class resources."""
    @classmethod
    @abstractmethod
    def create_screenshot(self, input_path: Path) -> Optional[Path]:
        """Get the screenshot of the ingested resource."""

    def _get_screenshot_from_pdf(self, path: Path) -> Path:
        """Get the screenshot from a PDF."""
        images = convert_from_path(path, last_page=1)
        for image in images:
            save_path = path.with_suffix(".png")
            image.save(save_path, format='png')
            return save_path
        logger.warning(f"Could not get screenshot from PDF {path}")

class PDF(ResourceScreenshotter):
    """Define the PDF screenshotter."""
    def create_screenshot(self, input_path: Path) -> Path:
        """Get the screenshot of the ingested PDF."""
        return self._get_screenshot_from_pdf(input_path)


class GenericText(ResourceScreenshotter):
    def create_screenshot(self, input_path: Path) -> Path:
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")


class Latex(ResourceScreenshotter):
    def create_screenshot(self, input_path: Path) -> Path:
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")


class Markdown(ResourceScreenshotter):
    def create_screenshot(self, input_path: Path) -> Path:
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")


class HTML(ResourceScreenshotter):
    def create_screenshot(self, input_path: Path) -> Path:
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")


class RawURL(ResourceScreenshotter):
    def create_screenshot(self, input_path: Path) -> Path:
        raise NotImplementedError(f"Screen-shotting method {self.__class__.__name__} not implemented.")