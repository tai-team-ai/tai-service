"""Define the API for the tai service."""
import sys
from pathlib import Path
from typing import Any
from mangum import Mangum
from main import create_app
try:
    from aws_lambda_typing.context import Context
    from aws_lambda_typing.events import APIGatewayProxyEventV2
except ImportError:
    Context = APIGatewayProxyEventV2 = Any

# add router directory to sys path for importing routers
base_dir = Path(__file__).parent
sys.path.insert(0, str(base_dir.resolve()))


def handler(event: APIGatewayProxyEventV2, context: Context) -> dict[str, str]:
    """Handle API Gateway event."""
    app = create_app()
    asgi_handler = Mangum(app)
    return asgi_handler(event, context)
