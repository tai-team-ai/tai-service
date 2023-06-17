"""Define the search database stack."""
from pathlib import Path
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    Duration,
    Size as StorageSize,
)
from tai_service.schemas import (
    AdminDocumentDBSettings,
    BasePineconeDBSettings,
)
from ..stack_helpers import retrieve_secret, get_secret_arn_from_name
from ..stack_config_models import StackConfigBaseModel
from ..constructs.document_db_construct import (
    DocumentDatabase,
    ElasticDocumentDBConfigModel,
)
from ..constructs.pinecone_db_construct import PineconeDatabase
from ..constructs.python_lambda_props_builder import (
    PythonLambdaPropsBuilderConfigModel,
)

MINIMUM_SUBNETS_FOR_DOCUMENT_DB = 3


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
        self._cdk_directory = Path(__file__).parent.parent
        self._custom_resource_dir = self._cdk_directory / "constructs/customresources"
        self.vpc = self._create_vpc()
        self._subnet_type_for_doc_db = ec2.SubnetType.PUBLIC
        self.document_db = self._get_document_db(doc_db_settings=doc_db_settings)
        self.pinecone_db = self._get_pinecone_db(pinecone_db_settings=pinecone_db_settings)

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
        db_config = ElasticDocumentDBConfigModel(
            cluster_name=doc_db_settings.cluster_name,
            admin_username=doc_db_settings.admin_user_name,
            admin_password=db_password,
            vpc=self.vpc,
            subnet_type=self._subnet_type_for_doc_db,
            tags=self._config.tags,
        )
        db_custom_resource_dir = self._custom_resource_dir / "document_db"
        lambda_config = PythonLambdaPropsBuilderConfigModel(
            function_name=self._namer("document-db-custom-resource"),
            description="Custom resource for performing CRUD operations on the document database",
            code_path=db_custom_resource_dir,
            handler_module_name="document_db_setup_lambda",
            handler_name="lambda_handler",
            runtime_environment=doc_db_settings,
            requirements_file_path=db_custom_resource_dir / "requirements.txt",
            files_to_copy_into_handler_dir=[
                self._cdk_directory.parent / "schemas.py",
                self._custom_resource_dir / "custom_resource_interface.py",
            ],
            vpc=self.vpc,
            subnet_type=self._subnet_type_for_doc_db,
            **self._get_global_custom_resource_lambda_config(),
        )
        db = DocumentDatabase(
            scope=self,
            construct_id=self._namer("document-db"),
            db_config=db_config,
            lambda_config=lambda_config,
        )
        return db

    def _get_pinecone_db(self, pinecone_db_settings: BasePineconeDBSettings) -> PineconeDatabase:
        pinecone_secret_arn = get_secret_arn_from_name(
            secret_name=pinecone_db_settings.secret_name,
            deployment_settings=self._config.deployment_settings,
        )
        db_custom_resource_dir = self._custom_resource_dir / "pinecone_db"
        lambda_config = PythonLambdaPropsBuilderConfigModel(
            function_name=self._namer("pinecone-db-custom-resource"),
            description="Custom resource for performing CRUD operations on the pinecone database",
            code_path=self._custom_resource_dir / "pinecone_db",
            handler_module_name="pinecone_db_setup_lambda",
            handler_name="lambda_handler",
            runtime_environment=pinecone_db_settings,
            requirements_file_path=db_custom_resource_dir / "requirements.txt",
            files_to_copy_into_handler_dir=[
                self._cdk_directory.parent / "schemas.py",
                self._custom_resource_dir / "custom_resource_interface.py",
            ],
            **self._get_global_custom_resource_lambda_config(),
        )
        db = PineconeDatabase(
            scope=self,
            construct_id=self._namer("pinecone-db"),
            pinecone_db_api_secret_arn=pinecone_secret_arn,
            lambda_config=lambda_config,
        )
        return db

    def _get_global_custom_resource_lambda_config(self) -> dict:
        config = {
            'timeout': Duration.minutes(3),
            'memory_size': 128,
            'ephemeral_storage_size': StorageSize.mebibytes(512),
        }
        return config
