"""Define the API for the tai service."""
from typing import Any
from mangum import Mangum
# first imports are for local development, second imports are for deployment
try:
    from .main import create_app
    from aws_lambda_typing.context import Context
    from aws_lambda_typing.events import APIGatewayProxyEventV2
except ImportError:
    from main import create_app
    Context = APIGatewayProxyEventV2 = Any

def handler(event: APIGatewayProxyEventV2, context: Context) -> dict[str, str]:
    """Handle API Gateway event."""
    app = create_app()
    asgi_handler = Mangum(app)
    return asgi_handler(event, context)
