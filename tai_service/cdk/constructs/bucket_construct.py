"""
Define a private bucket construct.

This construct create a private bucket that allows replication
and control over the removal policy.
"""

from typing import Optional
from pydantic import BaseModel, root_validator, Field
from aws_cdk import (
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
)


class BucketConstructModel(BaseModel):
    """Define the configuration for the bucket construct."""

    bucket_name: str = Field(
        ...,
        description="The name of the bucket to create.",
    )
    removal_policy: Optional[RemovalPolicy] = Field(
        default=RemovalPolicy.RETAIN,
        description="The removal policy for the bucket.",
    )
    bucket: s3.Bucket = Field(
        default=None,
        description="An existing bucket to use.",
    )

    class Config:
        """Define the Pydantic model configuration."""

        arbitrary_types_allowed = True

    @root_validator
    def validate_bucket(cls, values) -> dict:
        """Validate that only one bucket is defined."""
        if values["bucket"] is None and values["bucket_name"] is None:
            raise ValueError("Must define either bucket or bucket_name")
        return values

