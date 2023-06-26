"""Define the search database stack."""
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from ..stack_helpers import get_secret_arn_from_name, add_tags
from ..stack_config_models import StackConfigBaseModel
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
    DocumentDBSettings,
    MINIMUM_SUBNETS_FOR_DOCUMENT_DB,
)
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.customresources.pinecone_db.pinecone_db_custom_resource import PineconeDBSettings


class SearchServiceDatabases(Stack):
    """Define the search database stack."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        pinecone_db_settings: PineconeDBSettings,
        doc_db_settings: DocumentDBSettings,
    ) -> None:
        """Initialize the search database stack."""
        super().__init__(
            scope=scope,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._pinecone_db_settings = pinecone_db_settings
        self._doc_db_settings = doc_db_settings
        self._config = config
        self._namer = lambda name: f"{config.stack_id}-{name}"
        self._subnet_type_for_doc_db = ec2.SubnetType.PRIVATE_ISOLATED
        self.vpc = self._create_vpc()
        self.document_db = self._get_document_db(doc_db_settings=doc_db_settings)
        self.pinecone_db = self._get_pinecone_db()
        add_tags(self, config.tags)

    def _create_vpc(self) -> ec2.Vpc:
        subnet_configurations = []
        subnet_configurations.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-isolated"),
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            )
        )
        subnet_configurations.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-public"),
                subnet_type=ec2.SubnetType.PUBLIC,
            )
        )
        vpc = ec2.Vpc(
            scope=self,
            id=self._namer("vpc"),
            vpc_name=self._namer("vpc"),
            max_azs=3,
            nat_gateways=0,
            subnet_configuration=subnet_configurations,
        )
        return vpc

    def _get_document_db(self, doc_db_settings: DocumentDBSettings) -> DocumentDatabase:
        db_config = ElasticDocumentDBConfigModel(
            cluster_name=self._doc_db_settings.cluster_name,
            vpc=self.vpc,
            subnet_type=self._subnet_type_for_doc_db,
        )
        db = DocumentDatabase(
            scope=self,
            construct_id=self._namer("document-db"),
            db_setup_settings=doc_db_settings,
            db_config=db_config,
        )
        return db

    def _get_pinecone_db(self) -> PineconeDatabase:
        db = PineconeDatabase(
            scope=self,
            construct_id=self._namer("pinecone-db"),
            db_settings=self._pinecone_db_settings,
        )
        return db
