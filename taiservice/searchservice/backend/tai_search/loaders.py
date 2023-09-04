"""Define custom loaders for loading documents."""
from typing import TypedDict, Union, Any, Optional, Sequence, List
import re
import copy
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document
from langchain.document_loaders import (
    PyMuPDFLoader,
    MathpixPDFLoader,
    UnstructuredMarkdownLoader,
    BSHTMLLoader,
)
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from pytube import YouTube
from loguru import logger
from taiservice.searchservice.runtime_settings import SearchServiceSettings
from .data_ingestor_schema import InputFormat, IngestedDocument


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

    def _extract_links(self, text: str) -> list[str]:
        """Extract the links from the text."""
        links = re.findall(r"\[(.*?)\]\((.*?)\)", text)
        return [link[1] for link in links]

    def load(self) -> list[Document]:
        """Load PDF documents."""
        try:
            documents = self._math_pix_pdf_loader.load()
            for document in documents:
                links = self._extract_links(document.page_content)
                document.metadata["links"] = links
            return documents
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.warning(f"Mathpix failed to load {self.pdf_path}. Falling back to PyMuPDF.")
            return self._pymu_pdf_loader.load()




ALLOWED_SCHEMAS = {"http", "https"}
ALLOWED_NETLOCK = {
    "youtu.be",
    "m.youtube.com",
    "youtube.com",
    "www.youtube.com",
    "www.youtube-nocookie.com",
    "vid.plus",
}


class VideoInfo(TypedDict):
    """Define the video info."""
    title: str
    description: str
    view_count: int
    thumbnail_url: str
    publish_date: str
    length: int


class TranscriptPiece(TypedDict):
    """Define the transcript piece."""
    text: str
    start: float
    duration: float


# LangChain already has this loader built in. However, it's not useful for us
# as it's not extensible. We want to include timestamps in the metadata of each
# document, which isn't possible with the langchain version of this loader.
class YoutubeLoader(BaseLoader):
    """Loader that loads Youtube transcripts."""

    def __init__(
        self,
        video_id: str,
        add_video_info: bool = False,
        language: Union[str, Sequence[str]] = "en",
        translation: str = "en",
        continue_on_failure: bool = False,
    ):
        """Initialize with YouTube video ID."""
        self.video_id = video_id
        self.add_video_info = add_video_info
        self.language = language
        if isinstance(language, str):
            self.language = [language]
        else:
            self.language = language
        self.translation = translation
        self.continue_on_failure = continue_on_failure

    @classmethod
    def extract_video_id(cls, youtube_url: str) -> str:
        """Extract video id from common YT urls."""
        video_id = cls.parse_video_id(youtube_url)
        if not video_id:
            raise ValueError(
                f"Could not determine the video ID for the URL {youtube_url}"
            )
        return video_id

    @classmethod
    def from_youtube_url(cls, youtube_url: str, **kwargs: Any) -> 'YoutubeLoader':
        """Given youtube URL, load video."""
        video_id = cls.extract_video_id(youtube_url)
        return cls(video_id, **kwargs)

    def load(self) -> List[Document]:
        """Load documents."""
        metadata: dict[str, Any] = {"source": self.video_id}
        if self.add_video_info:
            # Get more video meta info
            # Such as title, description, thumbnail url, publish_date
            video_info = self._get_video_info()
            metadata.update(video_info) # type: ignore
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
        except TranscriptsDisabled:
            return []
        try:
            transcript = transcript_list.find_transcript(self.language)
        except NoTranscriptFound:
            en_transcript = transcript_list.find_transcript(["en"])
            transcript = en_transcript.translate(self.translation)
        transcript_pieces = transcript.fetch()
        # Original langchain code:
            # transcript = " ".join([t["text"].strip(" ") for t in transcript_pieces])
            # return [Document(page_content=transcript, metadata=metadata)]
        documents = []
        piece: TranscriptPiece
        for piece in transcript_pieces:
            metadata_copy = copy.deepcopy(metadata)
            metadata_copy["start"] = piece["start"]
            metadata_copy["duration"] = piece["duration"]
            documents.append(Document(page_content=piece["text"], metadata=metadata_copy))
        return documents

    @staticmethod
    def parse_video_id(url: str) -> Optional[str]:
        """Parse a youtube url and return the video id if valid, otherwise None."""
        parsed_url = urlparse(url)

        if parsed_url.scheme not in ALLOWED_SCHEMAS:
            return None

        if parsed_url.netloc not in ALLOWED_NETLOCK:
            return None

        path = parsed_url.path

        if path.endswith("/watch"):
            query = parsed_url.query
            parsed_query = parse_qs(query)
            if "v" in parsed_query:
                ids = parsed_query["v"]
                video_id = ids if isinstance(ids, str) else ids[0]
            else:
                return None
        else:
            path = parsed_url.path.lstrip("/")
            video_id = path.split("/")[-1]

        if len(video_id) != 11:  # Video IDs are 11 characters long
            return None
        return video_id

    def _get_video_info(self) -> VideoInfo:
        """Get important video information.

        Components are:
            - title
            - description
            - thumbnail url,
            - publish_date
            - channel_author
            - and more.
        """
        yt = YouTube(f"https://www.youtube.com/watch?v={self.video_id}")
        video_info: VideoInfo = {
            "title": yt.title or "Unknown",
            "description": yt.description or "Unknown",
            "view_count": yt.views or 0,
            "thumbnail_url": yt.thumbnail_url or "Unknown",
            "publish_date": yt.publish_date.strftime("%Y-%m-%d %H:%M:%S")
            if yt.publish_date
            else "Unknown",
            "length": yt.length or 0,
            "author": yt.author or "Unknown",
        }
        return video_info



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
    kwargs = {}
    if Loader == PDFLoader:
        secret = runtime_settings.mathpix_api_secret
        kwargs = secret.secret_value if secret else {}
    elif Loader == BSHTMLLoader:
        # the output of the BSHTMLLoader is generic text
        ingested_doc.input_format = InputFormat.GENERIC_TEXT
    loader = Loader(ingested_doc.data_pointer, **kwargs)
    copy_of_ingested_doc = copy.deepcopy(ingested_doc)
    copy_of_ingested_doc.loader = loader
    return copy_of_ingested_doc
