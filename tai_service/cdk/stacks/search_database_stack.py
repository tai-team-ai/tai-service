"""Define the search database stack."""

from aws_cdk import (
    Stack,
)
from ..stack_helpers import retrieve_secret
from ..stack_config_models import StackConfigBaseModel
from schemas import (
    AdminDocumentDBSettings,
    BasePineconeDBSettings,
)
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
)
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.python_lambda_props_builder import (
    PythonLambdaPropsBuilderConfigModel,
)


class SearchServiceDatabase(Stack):
    """Define the search database stack."""

    def __init__(
        self,
        config: StackConfigBaseModel,
        doc_db_settings: AdminDocumentDBSettings,
        pinecone_db_settings: BasePineconeDBSettings,
    ) -> None:
        """Initialize the search database stack."""
        super().__init__(
            scope=self,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._config = config
        self._namer = lambda name: f"{config.stack_id}-{name}"
        self.vpc = self._create_vpc()
        self.document_db = self._get_document_db()
        self.pinecone_db = self._get_pinecone_db()

    def _create_vpc(self) -> None:
        """Create the VPC for the document db."""
        pass

    def _get_document_db(self, doc_db_settings: AdminDocumentDBSettings) -> DocumentDatabase:
        """Get the document database."""
        db_password = retrieve_secret(
            secret_name=doc_db_settings.admin_user_password_secret_name,
            deployment_settings=self._config.deployment_settings,
        )
        config = ElasticDocumentDBConfigModel(
            cluster_name=doc_db_settings.cluster_name,
            admin_username=doc_db_settings.admin_user_name,
            admin_password=db_password,
            vpc=self.vpc,
            tags=self._config.tags,
        )
        doc_db = DocumentDatabase(
            scope=self,
            construct_id=self._namer("document-db"),
            db_config=config,
            lambda_config=self._get_custom_resource_lambda_config(),
        )
        return doc_db


    def _get_pinecone_db(self) -> PineconeDatabase:
        """Get the Pinecone database."""
        pass

    def _get_custom_resource_lambda_config(self) -> PythonLambdaPropsBuilderConfigModel:
        """Get the custom resource lambda config."""
        lambda_props = Py
