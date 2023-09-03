"""Define shared schemas for database models."""
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

try:
    from taiservice.api.routers.tai_schemas import ResourceSearchQuery, ClassResourceSnippet
except ImportError:
    from routers.tai_schemas import ResourceSearchQuery, ClassResourceSnippet


class BasePydanticModel(BaseModel):
    """
    Define the base model of the Pydantic model.

    This model extends the default dict method to convert all objects to strs.
    This is useful when using python packages that expect a serializable dict.
    """

    def _recurse_and_serialize(self, obj: Any, types_to_serialize: tuple) -> Any:
        """Recursively convert all objects to strs."""
        def serialize(v):
            if isinstance(v, types_to_serialize):
                return str(v)
            return v
        if isinstance(obj, dict):
            obj = {k: self._recurse_and_serialize(v, types_to_serialize) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            obj = [self._recurse_and_serialize(v, types_to_serialize) for v in obj]
        else:
            obj = serialize(obj)
        return obj

    def dict(self, *args, serialize_dates: bool = True, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(*args, **kwargs)
        types_to_serialize = (UUID, Enum)
        if serialize_dates:
            types_to_serialize += (datetime,)
        result = self._recurse_and_serialize(super_result, types_to_serialize)
        return result

    class Config:
        """Define the configuration for the Pydantic model."""

        use_enum_values = True
        allow_population_by_field_name = True


class DateRange(BasePydanticModel):
    """Define a schema for a date range."""
    start_date: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=7),
        description="The start date of the date range.",
    )
    end_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="The end date of the date range.",
    )


class SearchEngineResponse(ResourceSearchQuery):
    """Define the response from the search engine."""

    short_snippets: list[ClassResourceSnippet] = Field(
        ...,
        description="The short snippets of the class resources.",
    )
    long_snippets: list[ClassResourceSnippet] = Field(
        ...,
        description="The long snippets of the class resources.",
    )
