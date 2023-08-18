"""Define base configurations for the constructs."""
import json
from pathlib import Path
from enum import Enum
from pydantic import BaseSettings


class Permissions(str, Enum):
    """Define permissions for AWS resources."""

    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


class BaseDeploymentSettings(BaseSettings):
    """Define the base settings for the package."""

    def dict(self, *args, for_environment: bool=False, **kwargs):
        """Override the dict method to convert nested, dicts, sets and sequences to JSON."""
        output = super().dict(*args, **kwargs)
        if for_environment:
            new_output = {}
            for key, value in output.items():
                if hasattr(self.Config, "env_prefix"):
                    key = self.Config.env_prefix + key
                if isinstance(value, Enum):
                    value = value.value
                if isinstance(value, Path):
                    value = str(value.resolve())
                if isinstance(value, dict) or isinstance(value, list) or isinstance(value, set) or isinstance(value, tuple):
                    value = json.dumps(value)
                key = key.upper()
                new_output[key] = str(value)
            return new_output
        return output

    class Config:
        """Define the Pydantic config."""

        use_enum_values = True
        env_file = ".env"
        env_file_encoding = "utf-8"
