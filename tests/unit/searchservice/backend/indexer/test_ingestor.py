"""Define Tests to ensure that the ingestor module works as expected."""
from uuid import uuid4
from pydantic import ValidationError
import pytest
from taiservice.searchservice.backend.databases.document_db_schemas import (
    Metadata,
)
from taiservice.searchservice.backend.shared_schemas import (
    ClassResourceType,
)
from taiservice.searchservice.backend.tai_search.data_ingestor_schema import(
    IngestedDocument,
    LoadingStrategy,
    InputFormat,
)


def test_that_mismatched_loading_strategy_raises_error():
    """Test that mismatched loading strategy raises an error."""
    with pytest.raises(ValidationError):
        IngestedDocument(
            class_id=uuid4(),
            id=uuid4(),
            full_resource_url="https://www.google.com",
            data_pointer="https://www.google.com",
            input_format=InputFormat.PDF,
            metadata=Metadata(
                description="",
                resource_type=ClassResourceType.TEXTBOOK,
                title="",
                tags=[],
                total_page_count=0,
            ),
            loading_strategy=LoadingStrategy.UnstructuredMarkdownLoader,
        )
