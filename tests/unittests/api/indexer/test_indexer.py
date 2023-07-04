"""Define tests for the indexer module."""
from uuid import uuid4
from pydantic import ValidationError
import pytest
from taiservice.api.taibackend.indexer.indexer import (
    InputDocument,
    InputDataIngestStrategy,
    IngestedDocument,
    LoadingStrategy,
)

def test_that_empty_contents_with_embedded_ingest_type_raises():
    """Test that the contents can NOT be empty if the ingest type is embedded."""
    with pytest.raises(ValidationError):
        InputDocument(
            id=uuid4(),
            class_id=uuid4(),
            full_resource_url="https://www.google.com",
            metadata={},
            page_content=None,
            input_data_ingest_location=InputDataIngestStrategy.EMBEDDED_IN_DOCUMENT,
        )

def test_that_mismatched_loading_strategy_raises_error():
    """Test that mismatched loading strategy raises an error."""
    with pytest.raises(ValidationError):
        IngestedDocument(
            id=uuid4(),
            class_id=uuid4(),
            full_resource_url="https://www.google.com",
            metadata={},
            page_content=None,
            input_data_ingest_location=InputDataIngestStrategy.EMBEDDED_IN_DOCUMENT,
            loading_strategy=LoadingStrategy.PyMuPDF,
        )
