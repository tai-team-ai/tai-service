"""Define the base schema for the API models."""
from pydantic import BaseModel

def to_camel_case(string: str) -> str:
    init, *temp = string.split('_')
    return ''.join([init.lower(), *map(str.title, temp)])

class BasePydanticModel(BaseModel):
    """Define the base schema for the API models."""

    class Config:
        """Define the configuration for the base schema."""

        alias_generator = to_camel_case
        allow_population_by_field_name = True
        validate_assignment = True
