"""Define the search database stack."""
from pathlib import Path
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from tai_service.schemas import (
    AdminDocumentDBSettings,
    BasePineconeDBSettings,
)
from ..stack_helpers import retrieve_secret, get_secret_arn_from_name, add_tags
from ..stack_config_models import StackConfigBaseModel
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
)
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.customresources.pinecone_db.pinecone_db_setup_lambda import (
    PineconeDBSettings,
    PineconeIndexConfig,
    PodType,
    PodSize,
    DistanceMetric,
)


MINIMUM_SUBNETS_FOR_DOCUMENT_DB = 3
INDEXES = [
    # PineconeIndexConfig(
    #     name="tai-index",
    #     dimension=768,
    #     metric=DistanceMetric.DOT_PRODUCT,
    #     pod_instance_type=PodType.S1,
    #     pod_size=PodSize.X1,
    #     pods=1,
    #     replicas=1,
    # )
]
PINECONE_DB_SETTINGS = PineconeDBSettings(indexes=INDEXES)


class SearchServiceDatabases(Stack):
    """Define the search database stack."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
        doc_db_settings: AdminDocumentDBSettings,
        pinecone_db_settings: BasePineconeDBSettings,
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
        self._config = config
        self._namer = lambda name: f"{config.stack_id}-{name}"
        self._subnet_type_for_doc_db = ec2.SubnetType.PUBLIC
        self.vpc = self._create_vpc()
        # self.document_db = self._get_document_db(doc_db_settings=doc_db_settings)
        self.pinecone_db = self._get_pinecone_db(pinecone_db_settings=pinecone_db_settings)
        add_tags(self, config.tags)

    def _create_vpc(self) -> ec2.Vpc:
        # need to create enough subnets for the document db at a minimum
        subnet_configuration = []
        for i in range(MINIMUM_SUBNETS_FOR_DOCUMENT_DB):
            subnet_configuration.append(
                ec2.SubnetConfiguration(
                    name=self._namer(f"subnet-{i}"),
                    subnet_type=self._subnet_type_for_doc_db,
                )
            )
        subnet_configuration.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-private"),
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            )
        )
        subnet_configuration.append(
            ec2.SubnetConfiguration(
                name=self._namer("subnet-isolated"),
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
            )
        )
        vpc = ec2.Vpc(
            scope=self,
            id=self._namer("vpc"),
            vpc_name=self._namer("vpc"),
            max_azs=MINIMUM_SUBNETS_FOR_DOCUMENT_DB,
            nat_gateways=0,
        )
        return vpc

    def _get_document_db(self, doc_db_settings: AdminDocumentDBSettings) -> DocumentDatabase:
        db_password = retrieve_secret(
            secret_name=doc_db_settings.admin_user_password_secret_name,
            deployment_settings=self._config.deployment_settings,
        )
        admin_secret_arn = get_secret_arn_from_name(
            secret_name=doc_db_settings.admin_user_password_secret_name,
            deployment_settings=self._config.deployment_settings,
        )
        db_config = ElasticDocumentDBConfigModel(
            cluster_name=doc_db_settings.cluster_name,
            admin_username=doc_db_settings.admin_user_name,
            admin_password=db_password,
            admin_secret_arn=admin_secret_arn,
            vpc=self.vpc,
            subnet_type=self._subnet_type_for_doc_db,
        )
        db = DocumentDatabase(
            scope=self,
            construct_id=self._namer("document-db"),
            db_config=db_config,
        )
        return db

    def _get_pinecone_db(self, pinecone_db_settings: BasePineconeDBSettings) -> PineconeDatabase:
        pinecone_secret_arn = get_secret_arn_from_name(
            secret_name=pinecone_db_settings.api_key_secret_name,
            deployment_settings=self._config.deployment_settings,
        )
        db = PineconeDatabase(
            scope=self,
            construct_id=self._namer("pinecone-db"),
            pinecone_db_api_secret_arn=pinecone_secret_arn,
            db_settings=PINECONE_DB_SETTINGS,
        )
        return db

