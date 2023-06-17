"""Define the search database stack."""

from aws_cdk import (
    Stack,
)
from tai_service.cdk.constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
)
from tai_service.cdk.constructs.pinecone_db_construct import PineconeDatabase
from tai_service.cdk.constructs.python_lambda_props_builder import (
    PythonLambdaPropsBuilderConfigModel,
)


class SearchServiceDatabaseStack(Stack):
    """Define the search database stack."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        document_db_config: ElasticDocumentDBConfigModel,
        pinecone_db_api_secret_arn: str,
        **kwargs,
    ) -> None:
        """Initialize the search database stack."""
        super().__init__(scope, construct_id, **kwargs)
        self.document_db = self._get_document_db()

    def _get_document_db(self) -> DocumentDatabase:
        """Get the document database."""
        python_lambda_config = PythonLambdaPropsBuilderConfigModel(
            