"""Define custom splitters used for splitting documents."""
import copy
from typing import Optional, List, Any
from langchain.docstore.document import Document
from langchain.schema import Document
from langchain.text_splitter import Language, TextSplitter, RecursiveCharacterTextSplitter
from langchain import text_splitter
from ..shared_schemas import ChunkSize
from .data_ingestor_schema import InputFormat, IngestedDocument


class YouTubeTranscriptSplitter(RecursiveCharacterTextSplitter):
    """
    Implement a splitter for YouTube transcripts.

    We have chosen NOT to use the vanilla RecursiveCharacterTextSplitter
    as it doesn't handle timestamps. However, to keep this decoupled from
    the loader, we fall back to the RecursiveCharacterTextSplitter if the 
    appropriate metadata is not available in the document.

    NOTE: If the incoming document split sizes are already larger than
    the specified chunk size, then the document will not be split and a 
    warning will be logged.
    """
    def __init__(
        self,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create a new TextSplitter."""
        super().__init__(separators=separators, keep_separator=keep_separator, **kwargs)

    def create_documents(
        self, texts: List[str], metadatas: Optional[List[dict]] = None
    ) -> List[Document]:
        """Create a list of documents from the texts."""
        # first use all() to verify that all the texts have a "start_time"
        # if not, we should call the parent class
        if not metadatas:
            metadatas = [{} for _ in range(len(texts))]
        if not all("start_time" in metadata and "duration" in metadata for metadata in metadatas):
            return super().create_documents(texts=texts, metadatas=metadatas)

        documents = []
        aggregate_content = ""
        aggregate_duration = 0
        aggregate_start = None
        for i, text in enumerate(texts):
            metadata = copy.deepcopy(metadatas[i])
            if self._length_function(aggregate_content + text) <= self._chunk_size:
                aggregate_content += " " + text
                aggregate_duration += metadata["duration"]
                # set the start time of the first piece of the chunk, if it's not already set
                if aggregate_start is None:
                    aggregate_start = metadata["start"]
            else:
                metadata.update({"start": aggregate_start, "duration": aggregate_duration})
                documents.append(Document(page_content=aggregate_content.strip(), metadata=metadata))
                # start a new aggregate with the current piece
                aggregate_content = text
                aggregate_duration = metadata["duration"]
                aggregate_start = metadata["start"]

        # Don't forget to add the last aggregate if it's non-empty
        if aggregate_content:
            metadata = copy.deepcopy(metadatas[-1])
            metadata.update({"start": aggregate_start, "duration": aggregate_duration})
            documents.append(Document(page_content=aggregate_content, metadata=metadata))
        return documents


SPLITTER_STRATEGY_MAPPING = {
    InputFormat.PDF: Language.MARKDOWN, # Markdown is a superset of the RecursiveCharacterTextSplitter
    InputFormat.GENERIC_TEXT: RecursiveCharacterTextSplitter,
    InputFormat.LATEX: Language.LATEX,
    InputFormat.MARKDOWN: Language.MARKDOWN,
    InputFormat.HTML: Language.HTML,
    InputFormat.YOUTUBE_VIDEO: YouTubeTranscriptSplitter,
}
TOTAL_PAGE_COUNT_STRINGS = [
    "total_pages",
    "total_page_count",
    "total_page_counts",
    "page_count",
]
PAGE_NUMBER_STRINGS = ["page_number", "page_numbers", "page_num", "page_nums", "page"]


CHUNK_SIZE_TO_CHAR_COUNT_MAPPING = {
    ChunkSize.SMALL: 500,
    ChunkSize.LARGE: 2000,
}
OVERLAP_SIZE_TO_CHAR_COUNT_MAPPING = {
    ChunkSize.SMALL: 100,
    ChunkSize.LARGE: 300,
}


def get_total_page_count(docs: list[Document]) -> Optional[int]:
    """Get the page count and total page count."""
    for doc in docs:
        for key in TOTAL_PAGE_COUNT_STRINGS:
            if key in doc.metadata:
                return doc.metadata[key]


def get_page_number(doc: Document) -> Optional[int]:
    """Get the page number."""
    for key in PAGE_NUMBER_STRINGS:
        if key in doc.metadata:
            return doc.metadata[key]


def document_splitter_factory(ingested_document: IngestedDocument, chunk_size: ChunkSize) -> IngestedDocument:
    """Return a copy of the ingested document with the appropriate splitter."""
    strategy_instructions = SPLITTER_STRATEGY_MAPPING.get(ingested_document.input_format)
    kwargs = {
        "chunk_size": CHUNK_SIZE_TO_CHAR_COUNT_MAPPING[chunk_size],
        "chunk_overlap": OVERLAP_SIZE_TO_CHAR_COUNT_MAPPING[chunk_size],
    }
    if strategy_instructions is None:
        raise NotImplementedError(f"Splitter strategy for {ingested_document.input_format} not implemented.")
    if strategy_instructions in Language:
        return RecursiveCharacterTextSplitter.from_language(language=strategy_instructions, **kwargs)
    splitter: TextSplitter = getattr(text_splitter, strategy_instructions)(**kwargs)
    copy_of_ingested_document = ingested_document.copy()
    copy_of_ingested_document.splitter = splitter
    return copy_of_ingested_document
