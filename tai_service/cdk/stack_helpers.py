"""Define helpers for CDK stacks."""
from aws_cdk import Tags
from constructs import Construct

def add_tags(scope: Construct, tags: dict):
    """Add tags to a CDK stack.

    Args:
        scope (cdk.Construct): The CDK stack to add tags to.
        tags (dict): The tags to add to the stack.
    """
    for key, value in tags.items():
        Tags.of(scope).add(key, value)

