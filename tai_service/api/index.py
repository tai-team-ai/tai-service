"""Define the API for the tai service."""
from typing import Any
try:
    from aws_lambda_typing.context import Context
    from aws_lambda_typing.events import APIGatewayProxyEventV2
except ImportError:
    Context = APIGatewayProxyEventV2 = Any


def handler(event: APIGatewayProxyEventV2, context: Context) -> dict[str, str]:
    """Handle API Gateway event."""
    return {
        "statusCode": 200,
        "body": "Hello, World!",
    }