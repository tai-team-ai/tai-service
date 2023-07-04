"""Define tests for the indexer module."""
from uuid import uuid4
from pydantic import ValidationError
import pytest
from taiservice.api.taibackend.indexer.indexer import (
    InputDocument,
    InputDataIngestStrategy,
    IngestedDocument,
)


